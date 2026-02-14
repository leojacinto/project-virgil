import os
from typing import List, Dict, Optional
import logging
from pathlib import Path
import json

import PyPDF2
from docx import Document
import pandas as pd
import chromadb
from sentence_transformers import SentenceTransformer

from config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Store types
STORE_SERVICENOW = 'servicenow_assets'
STORE_CUSTOMER = 'customer_documents'
VALID_STORES = {STORE_SERVICENOW, STORE_CUSTOMER}

class DocumentProcessor:
    def __init__(self):
        self.vector_store_path = settings.vector_db_path
        self.upload_dir = settings.upload_dir
        
        self.chroma_client = chromadb.PersistentClient(path=self.vector_store_path)
        
        # Dual collections: ServiceNow reference assets + customer-specific documents
        self.collections = {}
        for store_name in VALID_STORES:
            try:
                self.collections[store_name] = self.chroma_client.get_or_create_collection(
                    name=store_name,
                    metadata={"hnsw:space": "cosine"}
                )
            except Exception as e:
                logger.error(f"Error creating collection {store_name}: {str(e)}")
                self.collections[store_name] = None
        
        # Backward compat: default collection points to customer_documents
        self.collection = self.collections.get(STORE_CUSTOMER)
        
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        
        self.metadata_file = os.path.join(self.vector_store_path, "metadata.json")
        self.metadata = self._load_metadata()
    
    def _get_collection(self, store: str = STORE_CUSTOMER):
        """Get the ChromaDB collection for the given store."""
        if store not in VALID_STORES:
            raise ValueError(f"Invalid store: {store}. Must be one of {VALID_STORES}")
        return self.collections.get(store)
    
    def _load_metadata(self) -> Dict:
        if os.path.exists(self.metadata_file):
            try:
                with open(self.metadata_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading metadata: {str(e)}")
        return {}
    
    def _save_metadata(self):
        try:
            with open(self.metadata_file, 'w') as f:
                json.dump(self.metadata, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving metadata: {str(e)}")
    
    def process_document(self, file_path: str) -> str:
        file_extension = Path(file_path).suffix.lower()
        
        try:
            if file_extension == '.pdf':
                return self._process_pdf(file_path)
            elif file_extension == '.docx':
                return self._process_docx(file_path)
            elif file_extension in ['.xlsx', '.xls', '.csv']:
                return self._process_spreadsheet(file_path)
            elif file_extension == '.txt':
                return self._process_text(file_path)
            else:
                raise ValueError(f"Unsupported file type: {file_extension}")
        except Exception as e:
            logger.error(f"Error processing document {file_path}: {str(e)}")
            raise
    
    def _process_pdf(self, file_path: str) -> str:
        text = ""
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
        return text.strip()
    
    def _process_docx(self, file_path: str) -> str:
        doc = Document(file_path)
        text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
        return text.strip()
    
    def _process_spreadsheet(self, file_path: str) -> str:
        file_extension = Path(file_path).suffix.lower()
        
        if file_extension == '.csv':
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path)
        
        text = df.to_string(index=False)
        return text
    
    def _process_text(self, file_path: str) -> str:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read().strip()
    
    def chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        chunks = []
        start = 0
        text_length = len(text)
        
        while start < text_length:
            end = start + chunk_size
            chunk = text[start:end]
            chunks.append(chunk)
            start = end - overlap
        
        return chunks
    
    def add_to_vector_store(self, file_id: str, content: str, filename: str, store: str = STORE_CUSTOMER, instance_name: str = None):
        collection = self._get_collection(store)
        if not collection:
            logger.error(f"Vector store collection not initialized for store: {store}")
            return
        
        try:
            chunks = self.chunk_text(content)
            
            embeddings = self.embedding_model.encode(chunks).tolist()
            
            ids = [f"{file_id}_chunk_{i}" for i in range(len(chunks))]
            metadatas = [{"file_id": file_id, "filename": filename, "chunk_index": i, "store": store,
                         "instance": instance_name or "unknown"} 
                        for i in range(len(chunks))]
            
            collection.add(
                embeddings=embeddings,
                documents=chunks,
                metadatas=metadatas,
                ids=ids
            )
            
            self.metadata[file_id] = {
                "filename": filename,
                "chunks": len(chunks),
                "content_length": len(content),
                "store": store,
                "instance": instance_name or "unknown"
            }
            self._save_metadata()
            
            logger.info(f"Added {len(chunks)} chunks from {filename} to {store}")
        except Exception as e:
            logger.error(f"Error adding to vector store: {str(e)}")
            raise
    
    def search_documents(self, query: str, top_k: int = 5, store: str = None) -> List[Dict]:
        """Search documents. If store is None, search both stores with source tagging."""
        try:
            query_embedding = self.embedding_model.encode([query]).tolist()
            
            stores_to_search = [store] if store else [STORE_SERVICENOW, STORE_CUSTOMER]
            all_documents = []
            
            for s in stores_to_search:
                collection = self._get_collection(s)
                if not collection:
                    continue
                
                try:
                    # Check if collection has any documents
                    if collection.count() == 0:
                        continue
                    
                    results = collection.query(
                        query_embeddings=query_embedding,
                        n_results=top_k
                    )
                    
                    if results['documents'] and len(results['documents']) > 0:
                        for i, doc in enumerate(results['documents'][0]):
                            metadata = results['metadatas'][0][i] if results['metadatas'] else {}
                            distance = results['distances'][0][i] if results['distances'] else 0
                            
                            source_label = 'ServiceNow Reference' if s == STORE_SERVICENOW else 'Customer Document'
                            all_documents.append({
                                "content": doc,
                                "filename": metadata.get("filename", "unknown"),
                                "file_id": metadata.get("file_id", "unknown"),
                                "relevance_score": 1 - distance,
                                "store": s,
                                "source_label": source_label,
                                "source_instance": metadata.get("instance", "unknown")
                            })
                except Exception as search_err:
                    logger.warning(f"Error searching {s}: {str(search_err)}")
            
            # Sort by relevance across both stores, return top_k
            all_documents.sort(key=lambda x: x['relevance_score'], reverse=True)
            return all_documents[:top_k]
        except Exception as e:
            logger.error(f"Error searching documents: {str(e)}")
            return []
    
    def list_documents(self, store: str = None) -> List[Dict]:
        """List documents. If store is None, return all. Otherwise filter by store."""
        documents = []
        for file_id, meta in self.metadata.items():
            doc_store = meta.get("store", STORE_CUSTOMER)  # backward compat: default to customer
            if store and doc_store != store:
                continue
            
            file_path = None
            for ext in settings.allowed_extensions:
                potential_path = os.path.join(self.upload_dir, f"{file_id}{ext}")
                if os.path.exists(potential_path):
                    file_path = potential_path
                    break
            
            documents.append({
                "file_id": file_id,
                "filename": meta.get("filename", "unknown"),
                "chunks": meta.get("chunks", 0),
                "content_length": meta.get("content_length", 0),
                "store": doc_store,
                "exists": file_path is not None
            })
        
        return documents
    
    def delete_document(self, file_id: str):
        try:
            # Determine which store this document belongs to
            doc_store = self.metadata.get(file_id, {}).get("store", STORE_CUSTOMER)
            collection = self._get_collection(doc_store)
            
            if collection:
                results = collection.get(where={"file_id": file_id})
                if results['ids']:
                    collection.delete(ids=results['ids'])
            
            if file_id in self.metadata:
                del self.metadata[file_id]
                self._save_metadata()
            
            for ext in settings.allowed_extensions:
                file_path = os.path.join(self.upload_dir, f"{file_id}{ext}")
                if os.path.exists(file_path):
                    os.remove(file_path)
            
            logger.info(f"Deleted document {file_id} from {doc_store}")
        except Exception as e:
            logger.error(f"Error deleting document: {str(e)}")
            raise
