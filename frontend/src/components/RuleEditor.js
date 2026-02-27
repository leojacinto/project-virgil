import React, { useState, useEffect, useCallback } from 'react';
import { Save, Plus, Trash2, X, ChevronDown, ChevronRight, AlertTriangle, CheckCircle2, Loader2 } from 'lucide-react';
import axios from 'axios';

const SECTION_KEYS = [
  { key: 'it4it_rules', label: 'IT4IT Value Stream Coverage' },
  { key: 'integration_rules', label: 'Integration Patterns' },
  { key: 'health_rules', label: 'Instance Health' },
  { key: 'adoption_rules', label: 'Adoption Maturity' },
  { key: 'security_rules', label: 'Security Posture' },
  { key: 'efficiency_rules', label: 'Platform Efficiency' },
];

const SOURCES = ['it4it', 'integration', 'best_practice'];
const SEVERITIES = ['critical', 'high', 'medium', 'low', 'info'];
const CHECK_TYPES = [
  { value: 'plugin_absent', label: 'Plugin Absent', fields: ['plugin'] },
  { value: 'plugin_present', label: 'Plugin Present', fields: ['plugin'] },
  { value: 'table_lte', label: 'Table Count ≤', fields: ['table', 'value'] },
  { value: 'table_eq', label: 'Table Count =', fields: ['table', 'value'] },
  { value: 'table_gt', label: 'Table Count >', fields: ['table', 'value'] },
  { value: 'table_between', label: 'Table In Range', fields: ['table', 'min', 'below'] },
  { value: 'table_exceeds', label: 'Table Exceeds Other', fields: ['table', 'other'] },
  { value: 'table_ratio_below', label: 'Table Ratio Below', fields: ['table', 'other', 'ratio'] },
  { value: 'cmdb_below', label: 'CMDB Field <', fields: ['field', 'value'] },
  { value: 'cmdb_gt', label: 'CMDB Field >', fields: ['field', 'value'] },
  { value: 'cmdb_flag_false', label: 'CMDB Flag False', fields: ['flag'] },
  { value: 'property_neq', label: 'Property ≠', fields: ['property', 'value'] },
  { value: 'property_prefix_absent', label: 'Property Prefix Absent', fields: ['prefix'] },
  { value: 'mid_server_eq', label: 'MID Server Count =', fields: ['count'] },
  { value: 'flow_count_eq', label: 'Flow Count =', fields: ['count'] },
];

function buildCheckObj(type, params) {
  if (type === 'plugin_absent') return { plugin_absent: params.plugin || '' };
  if (type === 'plugin_present') return { plugin_present: params.plugin || '' };
  if (type === 'table_lte') return { table_lte: { table: params.table || '', value: Number(params.value) || 0 } };
  if (type === 'table_eq') return { table_eq: { table: params.table || '', value: Number(params.value) || 0 } };
  if (type === 'table_gt') return { table_gt: { table: params.table || '', value: Number(params.value) || 0 } };
  if (type === 'table_between') return { table_between: { table: params.table || '', min: Number(params.min) || 0, below: Number(params.below) || 0 } };
  if (type === 'table_exceeds') return { table_exceeds: { table: params.table || '', other: params.other || '' } };
  if (type === 'table_ratio_below') return { table_ratio_below: { table: params.table || '', other: params.other || '', ratio: Number(params.ratio) || 0.5 } };
  if (type === 'cmdb_below') return { cmdb_below: { field: params.field || '', value: Number(params.value) || 0 } };
  if (type === 'cmdb_gt') return { cmdb_gt: { field: params.field || '', value: Number(params.value) || 0 } };
  if (type === 'cmdb_flag_false') return { cmdb_flag_false: params.flag || '' };
  if (type === 'property_neq') return { property_neq: { property: params.property || '', value: params.value || '' } };
  if (type === 'property_prefix_absent') return { property_prefix_absent: params.prefix || '' };
  if (type === 'mid_server_eq') return { mid_server_eq: Number(params.count) || 0 };
  if (type === 'flow_count_eq') return { flow_count_eq: Number(params.count) || 0 };
  return {};
}

function parseCheckType(check) {
  for (const ct of CHECK_TYPES) {
    if (check[ct.value] !== undefined) {
      const val = check[ct.value];
      const params = {};
      if (typeof val === 'string' || typeof val === 'number') {
        if (ct.fields[0] === 'plugin') params.plugin = val;
        else if (ct.fields[0] === 'flag') params.flag = val;
        else if (ct.fields[0] === 'prefix') params.prefix = val;
        else if (ct.fields[0] === 'count') params.count = val;
      } else if (typeof val === 'object') {
        Object.assign(params, val);
      }
      return { type: ct.value, params };
    }
  }
  if (check.all) return { type: 'all', nested: check.all };
  if (check.any) return { type: 'any', nested: check.any };
  return { type: 'unknown', params: {} };
}

function CheckEditor({ check, onChange, onRemove, depth = 0 }) {
  const parsed = parseCheckType(check);
  const ctDef = CHECK_TYPES.find(c => c.value === parsed.type);

  if (parsed.type === 'all' || parsed.type === 'any') {
    return (
      <div className={`border border-slate-200 dark:border-slate-600 rounded p-2 ${depth > 0 ? 'ml-3' : ''}`}>
        <div className="flex items-center justify-between mb-1">
          <select
            value={parsed.type}
            onChange={(e) => {
              const newType = e.target.value;
              const items = parsed.nested || [];
              onChange(newType === 'all' ? { all: items } : { any: items });
            }}
            className="text-[10px] bg-slate-100 dark:bg-slate-700 border-0 rounded px-1 py-0.5 font-semibold"
          >
            <option value="all">ALL OF</option>
            <option value="any">ANY OF</option>
          </select>
          <div className="flex items-center space-x-1">
            <button onClick={() => {
              const items = [...(parsed.nested || []), { plugin_absent: '' }];
              onChange(parsed.type === 'all' ? { all: items } : { any: items });
            }} className="text-[9px] text-indigo-600 hover:text-indigo-800 font-medium">+ Add</button>
            {onRemove && <button onClick={onRemove} className="text-red-400 hover:text-red-600"><Trash2 className="h-3 w-3" /></button>}
          </div>
        </div>
        <div className="space-y-1">
          {(parsed.nested || []).map((item, i) => (
            <CheckEditor
              key={i}
              check={item}
              depth={depth + 1}
              onChange={(newItem) => {
                const items = [...parsed.nested];
                items[i] = newItem;
                onChange(parsed.type === 'all' ? { all: items } : { any: items });
              }}
              onRemove={() => {
                const items = parsed.nested.filter((_, j) => j !== i);
                onChange(parsed.type === 'all' ? { all: items } : { any: items });
              }}
            />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className={`flex items-center space-x-1 flex-wrap ${depth > 0 ? 'ml-3' : ''}`}>
      <select
        value={parsed.type}
        onChange={(e) => {
          const newType = e.target.value;
          if (newType === 'all' || newType === 'any') {
            onChange(newType === 'all' ? { all: [check] } : { any: [check] });
          } else {
            onChange(buildCheckObj(newType, {}));
          }
        }}
        className="text-[9px] bg-slate-100 dark:bg-slate-700 border border-slate-200 dark:border-slate-600 rounded px-1 py-0.5"
      >
        {CHECK_TYPES.map(ct => <option key={ct.value} value={ct.value}>{ct.label}</option>)}
        <option value="all">ALL OF (group)</option>
        <option value="any">ANY OF (group)</option>
      </select>
      {ctDef && ctDef.fields.map(f => (
        <input
          key={f}
          type={['value', 'min', 'below', 'ratio', 'count'].includes(f) ? 'number' : 'text'}
          step={f === 'ratio' ? '0.1' : '1'}
          placeholder={f}
          value={parsed.params[f] ?? ''}
          onChange={(e) => {
            const newParams = { ...parsed.params, [f]: e.target.value };
            onChange(buildCheckObj(parsed.type, newParams));
          }}
          className="text-[9px] bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-600 rounded px-1.5 py-0.5 w-auto min-w-[80px] max-w-[160px]"
        />
      ))}
      {onRemove && <button onClick={onRemove} className="text-red-400 hover:text-red-600 flex-shrink-0"><Trash2 className="h-3 w-3" /></button>}
    </div>
  );
}

function EvalBlockEditor({ evalBlock, onChange }) {
  if (!evalBlock) {
    return (
      <div className="text-center py-2">
        <p className="text-[9px] text-slate-400 mb-1">No eval logic (scanner data not yet available)</p>
        <button
          onClick={() => onChange({ all: [{ plugin_absent: '' }] })}
          className="text-[9px] text-indigo-600 hover:text-indigo-800 font-medium"
        >+ Add Eval Block</button>
      </div>
    );
  }

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <p className="text-[9px] font-semibold text-indigo-600 dark:text-indigo-400 uppercase tracking-wider">Eval Logic</p>
        <button onClick={() => onChange(null)} className="text-[9px] text-red-400 hover:text-red-600">Remove Eval</button>
      </div>
      <CheckEditor check={evalBlock} onChange={onChange} />
    </div>
  );
}

function RuleForm({ rule, onChange, onDelete, isNew }) {
  const [expanded, setExpanded] = useState(isNew);

  const update = (field, value) => {
    onChange({ ...rule, [field]: value });
  };

  const inputCls = "text-[10px] w-full bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-600 rounded px-2 py-1";
  const labelCls = "text-[9px] font-medium text-slate-500 uppercase tracking-wider";

  return (
    <div className="border border-slate-200 dark:border-slate-600 rounded overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-3 py-2 flex items-center justify-between text-left hover:bg-slate-50 dark:hover:bg-slate-700/50 transition-colors"
      >
        <div className="flex items-center space-x-2">
          <span className={`inline-block w-1.5 h-1.5 rounded-full ${
            rule.severity === 'critical' ? 'bg-red-500' :
            rule.severity === 'high' ? 'bg-orange-500' :
            rule.severity === 'medium' ? 'bg-yellow-500' : 'bg-slate-400'
          }`} />
          <span className="text-[10px] font-mono text-slate-400">{rule.id || '(new)'}</span>
          <span className="text-[10px] font-medium text-slate-700 dark:text-slate-300">{rule.name || '(untitled)'}</span>
          {isNew && <span className="text-[8px] bg-emerald-100 text-emerald-700 px-1.5 py-0.5 rounded font-medium">NEW</span>}
        </div>
        {expanded ? <ChevronDown className="h-3 w-3 text-slate-400" /> : <ChevronRight className="h-3 w-3 text-slate-400" />}
      </button>
      {expanded && (
        <div className="px-3 py-2 bg-slate-50 dark:bg-slate-700/30 border-t border-slate-200 dark:border-slate-600 space-y-2">
          <div className="grid grid-cols-3 gap-2">
            <div>
              <label className={labelCls}>ID</label>
              <input value={rule.id || ''} onChange={e => update('id', e.target.value)} className={inputCls} placeholder="e.g. IT4IT-S2P-001" />
            </div>
            <div>
              <label className={labelCls}>Source</label>
              <select value={rule.source || 'best_practice'} onChange={e => update('source', e.target.value)} className={inputCls}>
                {SOURCES.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div>
              <label className={labelCls}>Severity</label>
              <select value={rule.severity || 'medium'} onChange={e => update('severity', e.target.value)} className={inputCls}>
                {SEVERITIES.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
          </div>
          <div>
            <label className={labelCls}>Name</label>
            <input value={rule.name || ''} onChange={e => update('name', e.target.value)} className={inputCls} placeholder="Rule name" />
          </div>
          <div>
            <label className={labelCls}>Category</label>
            <input value={rule.category || ''} onChange={e => update('category', e.target.value)} className={inputCls} placeholder="e.g. it4it_coverage" />
          </div>
          <div>
            <label className={labelCls}>Description</label>
            <textarea value={rule.description || ''} onChange={e => update('description', e.target.value)} className={inputCls + " h-12"} />
          </div>
          <div>
            <label className={labelCls}>Condition Description</label>
            <textarea value={rule.condition_description || ''} onChange={e => update('condition_description', e.target.value)} className={inputCls + " h-12"} />
          </div>
          <div>
            <label className={labelCls}>Recommendation</label>
            <textarea value={rule.recommendation || ''} onChange={e => update('recommendation', e.target.value)} className={inputCls + " h-16"} />
          </div>
          <div>
            <label className={labelCls}>Tags (comma-separated)</label>
            <input
              value={(rule.tags || []).join(', ')}
              onChange={e => update('tags', e.target.value.split(',').map(t => t.trim()).filter(Boolean))}
              className={inputCls}
              placeholder="e.g. S2P, spm, portfolio"
            />
          </div>

          {/* Eval Block Builder */}
          <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-600 rounded p-2">
            <EvalBlockEditor evalBlock={rule.eval || null} onChange={(newEval) => update('eval', newEval)} />
          </div>

          <div>
            <label className={labelCls}>Message Template</label>
            <input value={rule.message || ''} onChange={e => update('message', e.target.value)} className={inputCls} placeholder="Finding message (supports {placeholders})" />
          </div>
          <div>
            <label className={labelCls}>Recommended Nodes (JSON)</label>
            <input
              value={JSON.stringify(rule.recommended_nodes || {})}
              onChange={e => { try { update('recommended_nodes', JSON.parse(e.target.value)); } catch {} }}
              className={inputCls}
              placeholder='{"node_id": "reason"}'
            />
          </div>

          <div className="flex justify-end pt-1">
            <button onClick={onDelete} className="flex items-center space-x-1 text-[10px] text-red-500 hover:text-red-700 font-medium">
              <Trash2 className="h-3 w-3" />
              <span>Delete Rule</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function RuleEditor({ onClose, onSaved }) {
  const [yamlData, setYamlData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [saveResult, setSaveResult] = useState(null);
  const [expandedSection, setExpandedSection] = useState(null);

  const loadYaml = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get('/api/rules/yaml');
      setYamlData(res.data);
    } catch (err) {
      console.error('Failed to load rules YAML:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadYaml(); }, [loadYaml]);

  const updateRule = (sectionKey, index, updatedRule) => {
    const newData = { ...yamlData };
    newData[sectionKey] = [...(newData[sectionKey] || [])];
    newData[sectionKey][index] = updatedRule;
    setYamlData(newData);
    setDirty(true);
    setSaveResult(null);
  };

  const deleteRule = (sectionKey, index) => {
    const rule = yamlData[sectionKey][index];
    if (!window.confirm(`Delete rule ${rule.id || '(new)'}?`)) return;
    const newData = { ...yamlData };
    newData[sectionKey] = newData[sectionKey].filter((_, i) => i !== index);
    setYamlData(newData);
    setDirty(true);
    setSaveResult(null);
  };

  const addRule = (sectionKey) => {
    const newData = { ...yamlData };
    const section = newData[sectionKey] || [];
    section.push({
      id: '',
      name: '',
      description: '',
      source: sectionKey.includes('it4it') ? 'it4it' : sectionKey.includes('integration') ? 'integration' : 'best_practice',
      severity: 'medium',
      category: sectionKey.replace('_rules', ''),
      condition_description: '',
      recommendation: '',
      tags: [],
      eval: null,
      message: null,
      recommended_nodes: {},
    });
    newData[sectionKey] = section;
    setYamlData(newData);
    setDirty(true);
    setExpandedSection(sectionKey);
    setSaveResult(null);
  };

  const saveAll = async () => {
    setSaving(true);
    setSaveResult(null);
    try {
      const res = await axios.post('/api/rules/save', yamlData);
      setDirty(false);
      setSaveResult({ ok: true, total: res.data.total_rules });
      if (onSaved) onSaved();
    } catch (err) {
      setSaveResult({ ok: false, error: err.response?.data?.detail || err.message });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-5 w-5 animate-spin text-indigo-500" />
        <span className="ml-2 text-sm text-slate-500">Loading rules...</span>
      </div>
    );
  }

  if (!yamlData) {
    return <p className="text-sm text-red-500 py-4">Failed to load rules YAML.</p>;
  }

  const totalRules = SECTION_KEYS.reduce((sum, s) => sum + (yamlData[s.key]?.length || 0), 0);

  return (
    <div className="space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h4 className="text-sm font-semibold text-slate-800 dark:text-slate-200">Rule Editor</h4>
          <p className="text-[10px] text-slate-500">{totalRules} rules across {SECTION_KEYS.length} categories · {dirty ? 'Unsaved changes' : 'No changes'}</p>
        </div>
        <div className="flex items-center space-x-2">
          {saveResult && (
            <span className={`text-[10px] font-medium ${saveResult.ok ? 'text-emerald-600' : 'text-red-500'}`}>
              {saveResult.ok ? `Saved (${saveResult.total} rules)` : saveResult.error}
            </span>
          )}
          <button
            onClick={saveAll}
            disabled={!dirty || saving}
            className="flex items-center space-x-1 px-3 py-1.5 bg-indigo-600 text-white text-[10px] font-medium rounded hover:bg-indigo-700 disabled:opacity-40 transition-colors"
          >
            {saving ? <Loader2 className="h-3 w-3 animate-spin" /> : <Save className="h-3 w-3" />}
            <span>{saving ? 'Saving...' : 'Save to YAML'}</span>
          </button>
          <button onClick={onClose} className="p-1 text-slate-400 hover:text-slate-600">
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>

      {dirty && (
        <div className="flex items-center space-x-2 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded px-3 py-1.5">
          <AlertTriangle className="h-3.5 w-3.5 text-amber-500 flex-shrink-0" />
          <p className="text-[10px] text-amber-700 dark:text-amber-400">You have unsaved changes. Click "Save to YAML" to persist.</p>
        </div>
      )}

      {/* Rule Sections */}
      <div className="space-y-2">
        {SECTION_KEYS.map(({ key, label }) => {
          const rules = yamlData[key] || [];
          const isOpen = expandedSection === key;
          return (
            <div key={key} className="border border-slate-200 dark:border-slate-700 rounded-lg overflow-hidden">
              <button
                onClick={() => setExpandedSection(isOpen ? null : key)}
                className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-700/50 flex items-center justify-between hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors text-left"
              >
                <div className="flex items-center space-x-2">
                  {isOpen ? <ChevronDown className="h-3.5 w-3.5 text-slate-400" /> : <ChevronRight className="h-3.5 w-3.5 text-slate-400" />}
                  <span className="text-[11px] font-semibold text-slate-700 dark:text-slate-300">{label}</span>
                  <span className="text-[9px] text-slate-400 bg-slate-200 dark:bg-slate-600 px-1.5 py-0.5 rounded">{rules.length}</span>
                </div>
                <button
                  onClick={(e) => { e.stopPropagation(); addRule(key); }}
                  className="flex items-center space-x-1 text-[9px] text-indigo-600 hover:text-indigo-800 font-medium"
                >
                  <Plus className="h-3 w-3" />
                  <span>Add</span>
                </button>
              </button>
              {isOpen && (
                <div className="px-3 py-2 space-y-1">
                  {rules.length === 0 ? (
                    <p className="text-[10px] text-slate-400 text-center py-2">No rules in this section.</p>
                  ) : (
                    rules.map((rule, i) => (
                      <RuleForm
                        key={`${key}-${i}-${rule.id}`}
                        rule={rule}
                        isNew={!rule.id}
                        onChange={(updated) => updateRule(key, i, updated)}
                        onDelete={() => deleteRule(key, i)}
                      />
                    ))
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default RuleEditor;
