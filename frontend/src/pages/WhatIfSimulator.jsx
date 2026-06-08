import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Play, ShieldAlert, AlertCircle, Info, CheckCircle, 
  HelpCircle, RefreshCw, ChevronRight, History, Calendar,
  TrendingUp, Award, AlertTriangle, Scale, ListFilter
} from 'lucide-react';
import client from '../api/client';
import { useProjects } from '../context/ProjectContext';

const containerVariants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.05 } }
};

const itemVariants = {
  hidden: { opacity: 0, y: 15 },
  show: { opacity: 1, y: 0, transition: { type: 'spring', stiffness: 300, damping: 25 } }
};

const WhatIfSimulator = () => {
  const { projects, isLoadingProjects } = useProjects();
  const [selectedProjectId, setSelectedProjectId] = useState('');
  const [templates, setTemplates] = useState([]);
  const [history, setHistory] = useState([]);
  const [legalSummary, setLegalSummary] = useState(null);
  const [activeTab, setActiveTab] = useState('templates'); // 'templates' | 'history'
  
  // Simulation execution state
  const [isSimulating, setIsSimulating] = useState(false);
  const [simResult, setSimResult] = useState(null);
  const [customParams, setCustomParams] = useState({
    action: 'remove_field',
    field_code: 'PAI_GHG_SCOPE3',
    rationale: 'Company data unavailable'
  });
  
  const selectedProject = projects.find(p => p.id === selectedProjectId);

  // Fetch templates and history
  useEffect(() => {
    const fetchTemplates = async () => {
      try {
        const res = await client.get('/what-if/templates');
        setTemplates(res.data);
      } catch (err) {
        console.error('Failed to fetch templates', err);
      }
    };
    fetchTemplates();
  }, []);

  // Fetch project-specific data (history & summary)
  const fetchProjectData = async () => {
    if (!selectedProjectId) return;
    try {
      const [histRes, summaryRes] = await [
        await client.get(`/projects/${selectedProjectId}/what-if`),
        await client.get(`/projects/${selectedProjectId}/legal-summary`)
      ];
      setHistory(histRes.data);
      setLegalSummary(summaryRes.data);
    } catch (err) {
      console.error('Failed to fetch project what-if data', err);
    }
  };

  useEffect(() => {
    if (selectedProjectId) {
      fetchProjectData();
      setSimResult(null);
    }
  }, [selectedProjectId]);

  const handleRunSimulation = async (scenario) => {
    if (!selectedProjectId) return;
    setIsSimulating(true);
    setSimResult(null);
    try {
      const payload = {
        scenario_name: scenario.scenario_name,
        scenario_description: scenario.scenario_description,
        parameters: scenario.parameters
      };
      const res = await client.post(`/projects/${selectedProjectId}/what-if`, payload);
      setSimResult(res.data);
      fetchProjectData(); // Refresh history
      setActiveTab('result');
    } catch (err) {
      console.error('Simulation run failed', err);
      alert('Failed to execute what-if simulation.');
    } finally {
      setIsSimulating(false);
    }
  };

  // Helper for color coding the risk level
  const getRiskColor = (score) => {
    if (score >= 75) return { text: 'text-red-600', bg: 'bg-red-50', border: 'border-red-200', fill: '#ef4444' };
    if (score >= 45) return { text: 'text-orange-600', bg: 'bg-orange-50', border: 'border-orange-200', fill: '#f97316' };
    if (score >= 20) return { text: 'text-amber-600', bg: 'bg-amber-50', border: 'border-amber-200', fill: '#f59e0b' };
    return { text: 'text-emerald-600', bg: 'bg-emerald-50', border: 'border-emerald-200', fill: '#10b981' };
  };

  if (isLoadingProjects) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4">
        <div className="w-10 h-10 border-4 border-primary-200 border-t-primary-600 rounded-full animate-spin"></div>
        <div className="text-slate-500 font-bold">Loading simulator...</div>
      </div>
    );
  }

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex flex-col gap-6 w-full pb-10">
      
      {/* Top Context Bar */}
      <div className="glass-card px-6 py-4 flex flex-wrap justify-between items-center gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white shadow-lg shadow-indigo-500/30">
            <Scale size={20} strokeWidth={2.5} />
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-900">What-If Legal Risk Simulator</h1>
            <p className="text-sm font-medium text-slate-500">Test compliance scenarios, predict regulatory fines, and assess policy change impact.</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {projects.length > 0 && (
            <select 
              className="form-input bg-white/50 text-sm font-bold text-slate-700"
              value={selectedProjectId}
              onChange={(e) => setSelectedProjectId(e.target.value)}
            >
              <option value="" disabled>Select a Project...</option>
              {projects.map(p => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          )}
        </div>
      </div>

      {selectedProjectId ? (
        <motion.div variants={containerVariants} initial="hidden" animate="show" className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          
          {/* LEFT COLUMN: Summary Widget and Simulator Selector */}
          <div className="lg:col-span-1 flex flex-col gap-6">
            
            {/* Legal Summary Panel */}
            {legalSummary && (
              <motion.div variants={itemVariants} className="glass-card p-6 flex flex-col gap-4">
                <h3 className="font-bold text-slate-800 text-sm border-b border-slate-100 pb-3 flex justify-between items-center">
                  <span>Current Legal Risk Profile</span>
                  <span className="text-xs text-slate-400 font-medium">Live stats</span>
                </h3>
                
                <div className="flex items-center justify-between gap-4">
                  <div className="relative w-24 h-24 flex items-center justify-center shrink-0">
                    <svg className="w-full h-full transform -rotate-90">
                      <circle cx="48" cy="48" r="40" stroke="#f1f5f9" strokeWidth="8" fill="transparent" />
                      <circle 
                        cx="48" 
                        cy="48" 
                        r="40" 
                        stroke={getRiskColor(legalSummary.total_risk_score).fill} 
                        strokeWidth="8" 
                        fill="transparent" 
                        strokeDasharray={251.2}
                        strokeDashoffset={251.2 - (251.2 * legalSummary.total_risk_score) / 100}
                        strokeLinecap="round"
                        className="transition-all duration-1000 ease-out"
                      />
                    </svg>
                    <div className="absolute flex flex-col items-center">
                      <span className="text-xl font-black text-slate-800">{legalSummary.total_risk_score}%</span>
                      <span className="text-[8px] font-black text-slate-400 uppercase tracking-widest">Risk Index</span>
                    </div>
                  </div>
                  
                  <div className="flex-1 space-y-1">
                    <div className="flex justify-between text-xs font-semibold text-slate-600">
                      <span>Critical Gaps</span>
                      <span className="font-bold text-red-600">{legalSummary.critical_gaps}</span>
                    </div>
                    <div className="flex justify-between text-xs font-semibold text-slate-600">
                      <span>Escalation Warnings</span>
                      <span className="font-bold text-orange-600">{legalSummary.escalation_count}</span>
                    </div>
                    <div className="flex justify-between text-xs font-semibold text-slate-600 border-t border-slate-100 pt-1 mt-1">
                      <span>Compliant Fields</span>
                      <span className="font-bold text-emerald-600">{legalSummary.framework_coverage?.SFDR?.compliant || 0} / {legalSummary.total_fields}</span>
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-2 text-center text-[10px] font-bold mt-2">
                  <div className="bg-red-50 text-red-700 py-1.5 rounded-lg border border-red-100/50">
                    <div>High Risk</div>
                    <div className="text-sm font-black mt-0.5">{legalSummary.high_risk_fields}</div>
                  </div>
                  <div className="bg-amber-50 text-amber-700 py-1.5 rounded-lg border border-amber-100/50">
                    <div>Med Risk</div>
                    <div className="text-sm font-black mt-0.5">{legalSummary.medium_risk_fields}</div>
                  </div>
                  <div className="bg-emerald-50 text-emerald-700 py-1.5 rounded-lg border border-emerald-100/50">
                    <div>Low Risk</div>
                    <div className="text-sm font-black mt-0.5">{legalSummary.low_risk_fields}</div>
                  </div>
                </div>
              </motion.div>
            )}

            {/* Selector Card */}
            <motion.div variants={itemVariants} className="glass-card flex-1 flex flex-col overflow-hidden">
              <div className="border-b border-slate-100 bg-slate-50/50 flex">
                <button 
                  onClick={() => setActiveTab('templates')}
                  className={`flex-1 py-3 text-xs font-bold border-b-2 transition-all ${
                    activeTab === 'templates' 
                      ? 'border-indigo-600 text-indigo-700 bg-white' 
                      : 'border-transparent text-slate-500 hover:text-slate-700'
                  }`}
                >
                  Scenario Templates
                </button>
                <button 
                  onClick={() => setActiveTab('history')}
                  className={`flex-1 py-3 text-xs font-bold border-b-2 transition-all ${
                    activeTab === 'history' 
                      ? 'border-indigo-600 text-indigo-700 bg-white' 
                      : 'border-transparent text-slate-500 hover:text-slate-700'
                  }`}
                >
                  Simulation History ({history.length})
                </button>
              </div>

              <div className="p-4 flex-1 overflow-y-auto max-h-[500px] space-y-3">
                {activeTab === 'templates' && (
                  <>
                    {templates.map((tpl, i) => (
                      <div 
                        key={i}
                        className="p-4 bg-white border border-slate-200 rounded-xl hover:border-indigo-300 hover:shadow-sm transition-all cursor-pointer group flex flex-col gap-2"
                        onClick={() => handleRunSimulation(tpl)}
                      >
                        <div className="flex justify-between items-start">
                          <span className="font-bold text-sm text-slate-800 group-hover:text-indigo-600 transition-colors">{tpl.scenario_name}</span>
                          <span className="bg-indigo-50 text-indigo-700 p-1 rounded-lg shrink-0">
                            <Play size={12} fill="currentColor" />
                          </span>
                        </div>
                        <p className="text-xs font-medium text-slate-400 leading-relaxed">{tpl.scenario_description}</p>
                        <div className="flex items-center gap-1.5 text-[9px] font-bold text-slate-400 mt-1 uppercase tracking-wider bg-slate-50 py-1 px-2.5 rounded border w-fit">
                          Action: {tpl.parameters?.action?.replace('_', ' ')}
                        </div>
                      </div>
                    ))}
                  </>
                )}

                {activeTab === 'history' && (
                  <div className="space-y-3">
                    {history.length === 0 ? (
                      <div className="text-center text-xs text-slate-400 font-medium py-8">No simulation history found.</div>
                    ) : (
                      history.map((hist) => (
                        <div 
                          key={hist.id}
                          onClick={() => {
                            setSimResult(hist);
                            setActiveTab('result');
                          }}
                          className={`p-4 rounded-xl border cursor-pointer hover:shadow-sm transition-all ${
                            simResult?.id === hist.id 
                              ? 'border-indigo-500 bg-indigo-50/20' 
                              : 'border-slate-200 bg-white'
                          }`}
                        >
                          <div className="flex justify-between items-center gap-2 mb-1.5">
                            <span className="font-bold text-xs text-slate-800 line-clamp-1">{hist.scenario_name}</span>
                            <span className={`text-[10px] font-black px-2 py-0.5 rounded-full border ${
                              getRiskColor(hist.risk_score).bg
                            } ${getRiskColor(hist.risk_score).text} ${getRiskColor(hist.risk_score).border}`}>
                              Risk: {hist.risk_score}
                            </span>
                          </div>
                          <div className="flex items-center gap-3 text-[10px] font-medium text-slate-400">
                            <span className="flex items-center gap-1"><History size={10} /> {new Date(hist.created_at).toLocaleTimeString()}</span>
                            <span className="flex items-center gap-1"><Calendar size={10} /> {new Date(hist.created_at).toLocaleDateString()}</span>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                )}
              </div>
            </motion.div>
          </div>

          {/* RIGHT COLUMN: Simulator Active Outcome View */}
          <div className="lg:col-span-2 flex flex-col gap-6">
            
            <AnimatePresence mode="wait">
              {activeTab === 'result' && simResult ? (
                <motion.div
                  key="result-pane"
                  initial={{ opacity: 0, scale: 0.98 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.98 }}
                  className="glass-card p-6 flex flex-col gap-6"
                >
                  {/* Result Header */}
                  <div className="flex justify-between items-start border-b border-slate-100 pb-4 flex-wrap gap-4">
                    <div>
                      <div className="flex items-center gap-2 text-xs font-bold text-indigo-600 mb-1 uppercase tracking-wider">
                        <TrendingUp size={14} />
                        Simulation Outcome
                      </div>
                      <h2 className="text-xl font-bold text-slate-800">{simResult.scenario_name}</h2>
                      <p className="text-xs text-slate-400 font-medium mt-1">{simResult.scenario_description}</p>
                    </div>

                    <div className="flex items-center gap-3 bg-slate-50 border border-slate-200/50 p-2.5 rounded-xl">
                      <div className="flex flex-col">
                        <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Simulated Risk</span>
                        <span className={`text-xl font-black leading-none mt-1 ${getRiskColor(simResult.risk_score).text}`}>
                          {simResult.risk_score}/100
                        </span>
                      </div>
                      <div className="w-8 h-8 rounded-full flex items-center justify-center text-white font-black" style={{ backgroundColor: getRiskColor(simResult.risk_score).fill }}>
                        !
                      </div>
                    </div>
                  </div>

                  {/* Split panels: Triggered Obligations (Left) & Legal Consequences (Right) */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    
                    {/* Triggered Obligations */}
                    <div className="flex flex-col gap-3">
                      <h4 className="font-bold text-slate-800 text-sm flex items-center gap-2">
                        <ShieldAlert size={16} className="text-indigo-500" />
                        Triggered Regulatory Obligations
                      </h4>
                      <div className="space-y-2 max-h-[350px] overflow-y-auto pr-1">
                        {simResult.triggered_obligations?.map((ob, idx) => (
                          <div key={idx} className="p-3 bg-slate-50 border border-slate-200/60 rounded-xl flex flex-col gap-1">
                            <span className="font-bold text-xs text-slate-800 font-mono">{ob.regulation_article}</span>
                            <span className="text-xs text-slate-500 leading-relaxed font-medium">{ob.description}</span>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Legal Consequences */}
                    <div className="flex flex-col gap-3">
                      <h4 className="font-bold text-slate-800 text-sm flex items-center gap-2">
                        <AlertTriangle size={16} className="text-orange-500" />
                        Legal Fines & Enforcement Penalties
                      </h4>
                      <div className="space-y-3 max-h-[350px] overflow-y-auto pr-1">
                        {simResult.legal_consequences?.map((con, idx) => (
                          <div key={idx} className={`p-4 border rounded-xl flex items-start gap-2.5 ${
                            con.severity === 'Critical' || con.severity === 'High' ? 'bg-red-50/50 border-red-100' :
                            con.severity === 'Medium' ? 'bg-amber-50/50 border-amber-100' : 'bg-slate-50 border-slate-200'
                          }`}>
                            <AlertCircle size={16} className={`shrink-0 mt-0.5 ${
                              con.severity === 'Critical' || con.severity === 'High' ? 'text-red-500' :
                              con.severity === 'Medium' ? 'text-amber-500' : 'text-slate-400'
                            }`} />
                            <div className="flex flex-col gap-1 min-w-0">
                              <div className="flex justify-between items-center flex-wrap gap-1">
                                <span className="text-xs font-bold text-slate-800 uppercase tracking-wide">{con.type?.replace('_', ' ')}</span>
                                <span className={`text-[8px] font-black uppercase px-1.5 py-0.5 rounded ${
                                  con.severity === 'Critical' || con.severity === 'High' ? 'bg-red-100 text-red-700' :
                                  con.severity === 'Medium' ? 'bg-amber-100 text-amber-700' : 'bg-slate-200 text-slate-600'
                                }`}>
                                  {con.severity}
                                </span>
                              </div>
                              <span className="text-xs text-slate-500 leading-relaxed font-medium">{con.description}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>

                  {/* Remediation Playbooks / Action Items */}
                  {simResult.triggered_obligations && (
                    <div className="pt-4 border-t border-slate-100 flex flex-col gap-3">
                      <h4 className="font-bold text-slate-800 text-sm flex items-center gap-2">
                        <CheckCircle size={16} className="text-emerald-500" />
                        Actionable Remediation Playbook
                      </h4>
                      <div className="bg-slate-50 p-4 rounded-xl border border-slate-100 flex flex-col gap-2 font-medium text-xs text-slate-600 leading-relaxed">
                        <p>If this scenario occurs, the compliance team must perform the following actions immediately:</p>
                        <ul className="list-decimal pl-4 space-y-1 mt-1 text-slate-500 font-bold">
                          {simResult.triggered_obligations.filter(ob => ob.regulation_article === 'Remediation requirement').map((ob, idx) => (
                            <li key={idx}>{ob.description}</li>
                          ))}
                          {simResult.triggered_obligations.filter(ob => ob.regulation_article === 'Remediation requirement').length === 0 && (
                            <>
                              <li>Formally document the justification for non-disclosure in the compliance audit folder.</li>
                              <li>Prepare NCA notification draft using the switch templates.</li>
                              <li>Update investor relations communication package with a 30-day notice timeline.</li>
                            </>
                          )}
                        </ul>
                      </div>
                    </div>
                  )}
                  
                  <button 
                    onClick={() => setActiveTab('templates')}
                    className="btn btn-secondary w-full justify-center mt-2"
                  >
                    Back to Templates
                  </button>
                </motion.div>
              ) : (
                <motion.div
                  key="intro-pane"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="glass-card p-12 flex flex-col items-center justify-center flex-1 text-center min-h-[450px]"
                >
                  <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-100 to-purple-100 flex items-center justify-center mb-4 text-indigo-600">
                    <Scale size={32} />
                  </div>
                  <h3 className="text-lg font-bold text-slate-800 mb-2">Simulation Sandbox</h3>
                  <p className="text-slate-500 font-medium max-w-sm text-sm">
                    Select a scenario from the template folder on the left, or open history records to view legal consequences, triggered articles, and remediation playbooks.
                  </p>
                  <div className="mt-4 flex items-center gap-2 text-xs font-bold text-indigo-500">
                    <ChevronRight size={14} className="animate-pulse" />
                    <span>Run a template to test compliance limits</span>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

          </div>

        </motion.div>
      ) : (
        <div className="glass-card p-12 flex flex-col items-center justify-center text-center">
          <Scale size={48} className="text-slate-300 mb-4" />
          <h3 className="text-xl font-bold text-slate-800 mb-2">Select a Project</h3>
          <p className="text-slate-500 font-medium max-w-sm">Choose an active reporting project in the dropdown above to load the What-If simulation workspace.</p>
        </div>
      )}

    </motion.div>
  );
};

export default WhatIfSimulator;
