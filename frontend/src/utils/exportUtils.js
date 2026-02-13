import jsPDF from 'jspdf';
import html2canvas from 'html2canvas';

/**
 * Download Mermaid syntax as a .mmd file.
 * @param {string} code - The Mermaid diagram code
 * @param {string} filename - Filename without extension
 */
export const downloadMermaid = (code, filename = 'diagram') => {
  const blob = new Blob([code], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `${filename}.mmd`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
};

/**
 * Export a DOM element to a well-formatted PDF.
 * @param {HTMLElement} element - The DOM element to capture
 * @param {string} title - PDF title / filename
 * @param {object} options - Optional overrides
 */
export const exportToPDF = async (element, title = 'Export', options = {}) => {
  if (!element) return;

  const canvas = await html2canvas(element, {
    scale: 2,
    useCORS: true,
    logging: false,
    backgroundColor: '#ffffff',
    ...options.html2canvas,
  });

  const imgData = canvas.toDataURL('image/png');
  const imgWidth = canvas.width;
  const imgHeight = canvas.height;

  // A4 dimensions in points
  const pdfWidth = 595.28;
  const pdfHeight = 841.89;
  const margin = 40;
  const contentWidth = pdfWidth - margin * 2;
  const scaleFactor = contentWidth / imgWidth;
  const scaledHeight = imgHeight * scaleFactor;

  const pdf = new jsPDF({
    orientation: scaledHeight > pdfHeight * 1.2 ? 'portrait' : 'portrait',
    unit: 'pt',
    format: 'a4',
  });

  // Title
  pdf.setFontSize(16);
  pdf.setFont('helvetica', 'bold');
  pdf.text(title, margin, margin);

  // Timestamp
  pdf.setFontSize(9);
  pdf.setFont('helvetica', 'normal');
  pdf.setTextColor(120, 120, 120);
  pdf.text(`Generated: ${new Date().toLocaleString()}`, margin, margin + 18);
  pdf.setTextColor(0, 0, 0);

  const startY = margin + 35;
  const availableHeight = pdfHeight - startY - margin;

  if (scaledHeight <= availableHeight) {
    // Fits on one page
    pdf.addImage(imgData, 'PNG', margin, startY, contentWidth, scaledHeight);
  } else {
    // Multi-page: slice the source canvas into page-sized chunks
    const sliceHeight = availableHeight / scaleFactor; // height in source pixels per page
    let srcY = 0;
    let isFirstPage = true;

    while (srcY < imgHeight) {
      const thisSlice = Math.min(sliceHeight, imgHeight - srcY);
      // Create a canvas for this slice
      const sliceCanvas = document.createElement('canvas');
      sliceCanvas.width = imgWidth;
      sliceCanvas.height = thisSlice;
      const ctx = sliceCanvas.getContext('2d');
      ctx.drawImage(canvas, 0, srcY, imgWidth, thisSlice, 0, 0, imgWidth, thisSlice);

      const sliceImg = sliceCanvas.toDataURL('image/png');
      const sliceScaledH = thisSlice * scaleFactor;

      if (!isFirstPage) {
        pdf.addPage();
      }
      const yOffset = isFirstPage ? startY : margin;
      pdf.addImage(sliceImg, 'PNG', margin, yOffset, contentWidth, sliceScaledH);

      srcY += thisSlice;
      isFirstPage = false;
    }
  }

  pdf.save(`${title.replace(/[^a-zA-Z0-9_-]/g, '_')}.pdf`);
};
