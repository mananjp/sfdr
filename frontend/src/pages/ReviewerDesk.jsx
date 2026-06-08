import React, { useState, useEffect } from 'react';
import { FileText, CheckCircle, XCircle, AlertTriangle, Edit3, MessageSquare, ExternalLink, Loader } from 'lucide-react';
import { motion } from 'framer-motion';
import client from '../api/client';
import { useAuth } from '../context/AuthContext';
import { useProjects } from '../context/ProjectContext';

const ReviewerDesk = () => {
  const { currentUser } = useAuth();
  const { projects, isLoadingProjects } = useProjects();
  const [selectedProjectId, setSelectedProjectId] = useState('');
  const selectedProject = projects.find(p => p.id === selectedProjectId);
  const [matrixItems, setMatrixItems] = useState([]);
  const [isMatrixLoading, setIsMatrixLoading] = useState(false);
  const [selectedItem, setSelectedItem] = useState(null);
  const [draftText, setDraftText] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  // No auto-select, wait for user selection

  useEffect(() => {
    if (!selectedProjectId) return;
    const fetchMatrix = async () => {
      setIsMatrixLoading(true);
      try {
        const res = await client.get(`/projects/${selectedProjectId}/matrix`);
        setMatrixItems(res.data);
        if (res.data.length > 0) {
          setSelectedItem(res.data[0]);
          setDraftText(res.data[0].answer_text || '');
        } else {
          setSelectedItem(null);
          setDraftText('');
        }
      } catch (err) {
        console.error("Failed to fetch matrix", err);
      } finally {
        setIsMatrixLoading(false);
      }
    };
    fetchMatrix();
  }, [selectedProjectId]);

  const handleApprove = async () => {
    if (!selectedItem?.answer_id) return;
    setIsSaving(true);
    try {
      await client.post(`/answers/${selectedItem.answer_id}/approve?reviewer_id=${currentUser.id}`);
      // Update local state
      setMatrixItems(prev => prev.map(i => i.field_id === selectedItem.field_id ? { ...i, answer_status: 'Approved' } : i));
      setSelectedItem(prev => ({ ...prev, answer_status: 'Approved' }));
    } catch (err) {
      alert('Failed to approve');
    } finally {
      setIsSaving(false);
    }
  };

  const handleReject = async () => {
    if (!selectedItem?.answer_id) return;
    setIsSaving(true);
    try {
      await client.post(`/answers/${selectedItem.answer_id}/reject?reviewer_id=${currentUser.id}`);
      setMatrixItems(prev => prev.map(i => i.field_id === selectedItem.field_id ? { ...i, answer_status: 'Rejected' } : i));
      setSelectedItem(prev => ({ ...prev, answer_status: 'Rejected' }));
    } catch (err) {
      alert('Failed to reject');
    } finally {
      setIsSaving(false);
    }
  };

  const handleSaveDraft = async () => {
    if (!selectedItem?.answer_id) return;
    setIsSaving(true);
    try {
      await client.put(`/answers/${selectedItem.answer_id}`, {
        answer_text: draftText,
        status: 'Draft',
        approved_by_user_id: currentUser.id
      });
      setMatrixItems(prev => prev.map(i => i.field_id === selectedItem.field_id ? { ...i, answer_text: draftText, answer_status: 'Draft' } : i));
      setSelectedItem(prev => ({ ...prev, answer_text: draftText, answer_status: 'Draft' }));
      alert('Draft updated successfully');
    } catch (err) {
      alert('Failed to update draft');
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoadingProjects) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4">
        <div className="w-10 h-10 border-4 border-primary-200 border-t-primary-600 rounded-full animate-spin"></div>
        <div className="text-slate-500 font-bold">Loading Reviewer Desk...</div>
      </div>
    );
  }

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex flex-col gap-6 h-full min-h-[calc(100vh-8rem)]">
      
      {/* Top Context Bar */}
      <div className="glass-card px-6 py-4 flex flex-wrap justify-between items-center gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Reviewer Desk</h1>
          <p className="text-sm font-medium text-slate-500">Review, edit, and approve AI-generated compliance disclosures.</p>
        </div>
        <div className="flex items-center gap-3">
          {selectedProject?.status === 'Validating' && (
            <span className="badge badge-warning flex items-center gap-1.5 animate-pulse text-xs py-1 px-2.5">
              <Loader size={12} className="animate-spin" />
              Validating
            </span>
          )}
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

      {/* Main Split Layout */}
      <div className="flex flex-col lg:flex-row gap-6 h-full flex-1">
        
        {/* Left Sidebar - Fields List */}
        <div className="w-full lg:w-1/3 flex flex-col gap-4">
          <div className="glass-card flex-1 flex flex-col overflow-hidden max-h-[800px]">
            <div className="p-4 border-b border-slate-100 bg-white/40">
              <h3 className="font-bold text-slate-800 flex items-center justify-between">
                Pending Reviews
                <span className="bg-primary-100 text-primary-700 py-0.5 px-2.5 rounded-full text-xs font-black">
                  {matrixItems.filter(i => i.answer_status !== 'Approved').length}
                </span>
              </h3>
            </div>
            
            <div className="overflow-y-auto flex-1 p-2 space-y-2">
              {isMatrixLoading ? (
                <div className="flex flex-col items-center justify-center h-40 gap-3">
                  <div className="w-8 h-8 border-4 border-slate-200 border-t-primary-600 rounded-full animate-spin"></div>
                  <span className="text-slate-500 font-bold text-sm">Loading reviews...</span>
                </div>
              ) : !selectedProjectId ? (
                <div className="p-4 text-center text-sm text-slate-500 font-medium">Please select a project above.</div>
              ) : matrixItems.length === 0 ? (
                <div className="p-4 text-center text-sm text-slate-500 font-medium">No disclosures found.</div>
              ) : matrixItems.map(item => (
                <div 
                  key={item.field_id}
                  onClick={() => {
                    setSelectedItem(item);
                    setDraftText(item.answer_text || '');
                  }}
                  className={`p-4 rounded-xl cursor-pointer border-2 transition-all ${
                    selectedItem?.field_id === item.field_id 
                      ? 'border-indigo-500 bg-indigo-50/50 shadow-md shadow-indigo-100' 
                      : 'border-transparent hover:bg-slate-50/80 bg-white/40 shadow-sm'
                  }`}
                >
                  <div className="flex justify-between items-start gap-2 mb-2">
                    <span className="font-bold text-sm text-slate-800 line-clamp-2">{item.field_label}</span>
                    <span className={`text-[10px] uppercase tracking-wider font-bold px-2 py-1 rounded-md shrink-0 ${
                      item.answer_status === 'Approved' ? 'bg-emerald-100 text-emerald-700' : 
                      item.answer_status === 'Draft' ? 'bg-indigo-100 text-indigo-700' : 'bg-rose-100 text-rose-700'
                    }`}>
                      {item.answer_status}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-xs font-medium text-slate-500">
                    <span className="font-mono bg-white px-1.5 rounded">{item.field_code}</span>
                    {item.validation_passed ? (
                      <span className="text-emerald-600 flex items-center gap-1"><CheckCircle size={12}/> Valid</span>
                    ) : (
                      <span className="text-rose-600 flex items-center gap-1"><AlertTriangle size={12}/> Issues</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Content - Review Editor */}
        <div className="w-full lg:w-2/3 flex flex-col gap-6">
          {selectedItem ? (
            <>
              {/* Field Metadata and Legal Info */}
              <div className="glass-card p-6 flex flex-col gap-4">
                <h2 className="font-bold text-lg text-slate-800 line-clamp-2">{selectedItem.field_label}</h2>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                  <div className="bg-slate-50 rounded-lg px-3 py-2">
                    <div className="font-bold text-slate-400 uppercase tracking-wider text-[10px]">Framework & Code</div>
                    <div className="font-mono text-slate-700 mt-0.5">{selectedItem.framework || 'SFDR'} ({selectedItem.field_code})</div>
                  </div>
                  <div className="bg-slate-50 rounded-lg px-3 py-2">
                    <div className="font-bold text-slate-400 uppercase tracking-wider text-[10px]">Legal Basis</div>
                    <div className="font-bold text-slate-700 mt-0.5">{selectedItem.legal_basis || 'SFDR RTS'}</div>
                  </div>
                  <div className="bg-slate-50 rounded-lg px-3 py-2">
                    <div className="font-bold text-slate-400 uppercase tracking-wider text-[10px]">Enforcement Body</div>
                    <div className="font-bold text-slate-700 mt-0.5">{selectedItem.enforcement_body || 'NCA / ESMA'}</div>
                  </div>
                  <div className="bg-slate-50 rounded-lg px-3 py-2 flex flex-col justify-center">
                    <div className="font-bold text-slate-400 uppercase tracking-wider text-[10px] mb-0.5">Penalty Tier</div>
                    <span className={`inline-block font-extrabold text-[10px] w-fit px-2 py-0.5 rounded border ${
                      selectedItem.penalty_tier === 'Critical' ? 'bg-red-50 text-red-700 border-red-200' :
                      selectedItem.penalty_tier === 'High' ? 'bg-orange-50 text-orange-700 border-orange-200' :
                      selectedItem.penalty_tier === 'Medium' ? 'bg-amber-50 text-amber-700 border-amber-200' :
                      'bg-emerald-50 text-emerald-700 border-emerald-200'
                    }`}>
                      {selectedItem.penalty_tier || 'Medium'}
                    </span>
                  </div>
                </div>

                {selectedItem.cross_references && selectedItem.cross_references.length > 0 && (
                  <div className="flex flex-col gap-1.5 pt-2 border-t border-slate-100">
                    <div className="font-bold text-slate-400 uppercase tracking-wider text-[10px]">Cross-Framework Equivalents</div>
                    <div className="flex flex-wrap gap-2">
                      {selectedItem.cross_references.map((ref, idx) => (
                        <span key={idx} className="inline-flex items-center gap-1.5 text-xs font-bold bg-indigo-50 text-indigo-700 rounded-lg px-2.5 py-1 border border-indigo-100">
                          🔗 {ref.framework}: {ref.field_code} ({ref.relationship})
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Evidence Panel */}
              <div className="glass-card p-6 border-l-4 border-l-indigo-500">
                <div className="flex justify-between items-start mb-4">
                  <h3 className="font-bold text-lg text-slate-800 flex items-center gap-2">
                    <FileText size={20} className="text-indigo-500" />
                    Source Evidence
                  </h3>
                  <div className="bg-indigo-50 px-3 py-1 rounded-full border border-indigo-100 flex items-center gap-2 text-xs font-bold text-indigo-700">
                    Confidence: {Math.round((selectedItem.confidence || 0) * 100)}%
                  </div>
                </div>
                
                <div className="bg-slate-50 p-4 rounded-xl border border-slate-100 font-serif text-slate-700 italic relative">
                  <div className="absolute top-4 left-4 text-4xl text-indigo-200 font-serif leading-none">"</div>
                  <p className="relative z-10 pl-6 leading-relaxed">
                    {selectedItem.evidence_quote || "No evidence quote found."}
                  </p>
                </div>
                
                <div className="mt-4 flex items-center gap-4 text-sm font-medium text-slate-500">
                  <span className="flex items-center gap-1.5"><FileText size={14} /> {selectedItem.source_file || 'Unknown'}</span>
                  <span className="flex items-center gap-1.5"><ExternalLink size={14} /> Page {selectedItem.page_no || 'Unknown'}</span>
                </div>
              </div>

              {/* Drafting Panel */}
              <div className="glass-card p-6 flex flex-col flex-1">
                <div className="flex justify-between items-center mb-4">
                  <h3 className="font-bold text-lg text-slate-800 flex items-center gap-2">
                    <Edit3 size={20} className="text-indigo-500" />
                    Disclosure Draft
                  </h3>
                </div>
                
                <textarea 
                  value={draftText}
                  onChange={(e) => setDraftText(e.target.value)}
                  className="form-input flex-1 min-h-[250px] p-4 bg-slate-50/50 resize-none font-medium text-slate-700 text-sm leading-relaxed"
                  placeholder="Review the AI-generated draft here..."
                ></textarea>

                {/* Enriched Validation Legal Consequences & Remediation Alerts */}
                {selectedItem.legal_consequences && selectedItem.legal_consequences.length > 0 && (
                  <div className="mt-4 space-y-3">
                    {selectedItem.legal_consequences.map((conseq, idx) => (
                      <div key={idx} className={`p-4 border rounded-xl flex items-start gap-3 ${
                        conseq.severity === 'Error' ? 'bg-red-50/70 border-red-100' : 'bg-orange-50/70 border-orange-100'
                      }`}>
                        <AlertTriangle size={20} className={conseq.severity === 'Error' ? 'text-red-500 shrink-0 mt-0.5' : 'text-orange-500 shrink-0 mt-0.5'} />
                        <div className="flex-1 min-w-0">
                          <div className="flex justify-between items-center flex-wrap gap-2">
                            <span className={`font-bold text-sm ${conseq.severity === 'Error' ? 'text-red-900' : 'text-orange-900'}`}>{conseq.message}</span>
                            {conseq.escalation_required && (
                              <span className="bg-red-600 text-white font-extrabold text-[9px] px-2 py-0.5 rounded tracking-wide uppercase">
                                Escalation Required
                              </span>
                            )}
                          </div>
                          <div className="mt-2 text-xs font-medium text-slate-500 flex flex-col gap-1">
                            <div><strong>Regulation Article:</strong> {conseq.regulation_ref}</div>
                            <div><strong>Legal Consequence:</strong> {conseq.legal_consequence}</div>
                            <div><strong>Potential Fines:</strong> {conseq.penalty_range}</div>
                            <div className="mt-2 p-3 bg-white border border-slate-100 rounded-lg font-mono text-[11px] leading-relaxed text-slate-600">
                              <strong className="text-slate-800">Remediation Playbook:</strong>
                              <div className="mt-1 whitespace-pre-wrap">{conseq.remediation}</div>
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Action Buttons */}
                <div className="mt-6 flex justify-between items-center pt-6 border-t border-slate-100">
                  <button 
                    onClick={handleReject}
                    disabled={isSaving}
                    className="btn bg-white hover:bg-rose-50 text-rose-600 border border-slate-200 hover:border-rose-200"
                  >
                    <XCircle size={18} /> Reject
                  </button>
                  <div className="flex gap-3">
                    <button 
                      onClick={handleSaveDraft}
                      disabled={isSaving}
                      className="btn btn-secondary"
                    >
                      Save Draft
                    </button>
                    <button 
                      onClick={handleApprove}
                      disabled={isSaving}
                      className="btn btn-primary"
                    >
                      <CheckCircle size={18} /> Approve Disclosure
                    </button>
                  </div>
                </div>
              </div>
            </>
          ) : (
            <div className="glass-card p-12 flex flex-col items-center justify-center flex-1 text-center">
              <MessageSquare size={48} className="text-slate-300 mb-4" />
              <h3 className="text-xl font-bold text-slate-800 mb-2">Select a field to review</h3>
              <p className="text-slate-500 font-medium max-w-sm">Choose a disclosure requirement from the left sidebar to view evidence and edit drafts.</p>
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
};

export default ReviewerDesk;
