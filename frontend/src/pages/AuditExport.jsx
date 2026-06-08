import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Download, FileText, Code2, Eye, EyeOff, ChevronDown, Check,
  Loader, AlertTriangle, Package, Sparkles, Shield, Printer,
  Copy, CheckCircle, BookOpen, ArrowRight, RefreshCw
} from 'lucide-react';
import client from '../api/client';
import { useProjects } from '../context/ProjectContext';

const containerVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.08 }
  }
};

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { type: 'spring', stiffness: 300, damping: 24 } }
};

const AuditExport = () => {
  const { projects, isLoadingProjects } = useProjects();
  const [selectedProjectId, setSelectedProjectId] = useState('');
  const [activeTab, setActiveTab] = useState('markdown'); // 'markdown' | 'html'
  const [markdownContent, setMarkdownContent] = useState('');
  const [htmlContent, setHtmlContent] = useState('');
  const [isLoadingMd, setIsLoadingMd] = useState(false);
  const [isLoadingHtml, setIsLoadingHtml] = useState(false);
  const [error, setError] = useState(null);
  const [showPreview, setShowPreview] = useState(true);
  const [copied, setCopied] = useState(false);
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const dropdownRef = useRef(null);
  const htmlPreviewRef = useRef(null);

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setIsDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const selectedProject = projects.find(p => p.id === selectedProjectId);

  const fetchExport = async (format) => {
    if (!selectedProjectId) return;
    setError(null);

    if (format === 'markdown') {
      setIsLoadingMd(true);
      try {
        const res = await client.get(`/projects/${selectedProjectId}/export/markdown`, {
          responseType: 'text',
          transformResponse: [(data) => data],
        });
        setMarkdownContent(res.data);
      } catch (err) {
        console.error('MD export error:', err);
        setError('Failed to generate Markdown export. Make sure the project has processed data.');
      } finally {
        setIsLoadingMd(false);
      }
    } else {
      setIsLoadingHtml(true);
      try {
        const res = await client.get(`/projects/${selectedProjectId}/export/html`, {
          responseType: 'text',
          transformResponse: [(data) => data],
        });
        setHtmlContent(res.data);
      } catch (err) {
        console.error('HTML export error:', err);
        setError('Failed to generate HTML export. Make sure the project has processed data.');
      } finally {
        setIsLoadingHtml(false);
      }
    }
  };

  // Fetch both formats when a project is selected
  useEffect(() => {
    if (selectedProjectId) {
      setMarkdownContent('');
      setHtmlContent('');
      fetchExport('markdown');
      fetchExport('html');
    }
  }, [selectedProjectId]);

  const handleDownload = (format) => {
    const content = format === 'markdown' ? markdownContent : htmlContent;
    const ext = format === 'markdown' ? 'md' : 'html';
    const mime = format === 'markdown' ? 'text/markdown' : 'text/html';
    const projectName = selectedProject?.name?.replace(/\s+/g, '_') || 'export';

    const blob = new Blob([content], { type: `${mime};charset=utf-8` });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `SFDR_Disclosure_${projectName}_${new Date().toISOString().split('T')[0]}.${ext}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleCopy = async () => {
    const content = activeTab === 'markdown' ? markdownContent : htmlContent;
    if (!content) return;
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback
      const textarea = document.createElement('textarea');
      textarea.value = content;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handlePrint = () => {
    if (activeTab === 'html' && htmlContent) {
      const printWindow = window.open('', '_blank');
      printWindow.document.write(htmlContent);
      printWindow.document.close();
      printWindow.focus();
      printWindow.print();
    }
  };

  const handleRefresh = () => {
    if (selectedProjectId) {
      fetchExport(activeTab);
    }
  };

  const currentContent = activeTab === 'markdown' ? markdownContent : htmlContent;
  const isCurrentLoading = activeTab === 'markdown' ? isLoadingMd : isLoadingHtml;

  return (
    <div className="flex flex-col gap-8 w-full relative">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4"
      >
        <div>
          <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center text-white shadow-lg shadow-violet-500/30">
              <Package size={20} strokeWidth={2.5} />
            </div>
            Audit-Ready Exports
          </h1>
          <p className="text-slate-500 mt-1.5 font-medium">
            Generate & download disclosure packages with evidence citations, summaries, and reviewer sign-off sections.
          </p>
        </div>
      </motion.div>

      {/* Project Selector + Controls */}
      <motion.div
        variants={containerVariants}
        initial="hidden"
        animate="show"
        className="grid grid-cols-1 lg:grid-cols-3 gap-6"
      >
        {/* Left: Project Selector Card */}
        <motion.div variants={itemVariants} className="lg:col-span-1">
          <div className="glass-card p-6 flex flex-col gap-5 h-full">
            <div className="flex items-center gap-2 text-sm font-bold text-slate-600">
              <Shield size={16} className="text-violet-500" />
              Select Project
            </div>

            {/* Custom Project Dropdown */}
            <div className="relative" ref={dropdownRef}>
              <button
                onClick={() => setIsDropdownOpen(!isDropdownOpen)}
                disabled={isLoadingProjects}
                className="w-full flex items-center justify-between gap-2 px-4 py-3.5 bg-white border border-slate-200 rounded-xl text-left hover:border-primary-300 focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-400 transition-all text-sm font-medium text-slate-700 disabled:opacity-50"
              >
                <span className={selectedProjectId ? 'text-slate-800' : 'text-slate-400'}>
                  {isLoadingProjects ? 'Loading projects...' : selectedProject ? selectedProject.name : 'Choose a project to export'}
                </span>
                <ChevronDown size={16} className={`text-slate-400 transition-transform ${isDropdownOpen ? 'rotate-180' : ''}`} />
              </button>

              <AnimatePresence>
                {isDropdownOpen && (
                  <motion.div
                    initial={{ opacity: 0, y: -4, scale: 0.98 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: -4, scale: 0.98 }}
                    transition={{ duration: 0.15 }}
                    className="absolute z-50 top-full left-0 right-0 mt-2 bg-white border border-slate-200 rounded-xl shadow-xl shadow-slate-900/10 overflow-hidden max-h-64 overflow-y-auto"
                  >
                    {projects.length === 0 ? (
                      <div className="px-4 py-6 text-center text-sm text-slate-400 font-medium">
                        No projects found. Create one from Dashboard.
                      </div>
                    ) : (
                      projects.map((p) => (
                        <button
                          key={p.id}
                          onClick={() => {
                            setSelectedProjectId(p.id);
                            setIsDropdownOpen(false);
                          }}
                          className={`w-full flex items-center justify-between gap-3 px-4 py-3 text-left text-sm hover:bg-primary-50 transition-colors border-b border-slate-50 last:border-b-0 ${
                            selectedProjectId === p.id ? 'bg-primary-50/70' : ''
                          }`}
                        >
                          <div className="flex flex-col min-w-0">
                            <span className="font-semibold text-slate-800 truncate">{p.name}</span>
                            <span className="text-xs text-slate-400 font-medium mt-0.5">
                              {p.disclosure_type} · {p.document_count} docs · {p.progress}% complete
                            </span>
                          </div>
                          <div className="flex items-center gap-2 shrink-0">
                            <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-md ${
                              p.status === 'Completed' ? 'bg-emerald-50 text-emerald-600' :
                              p.status === 'Validating' ? 'bg-amber-50 text-amber-600' :
                              'bg-slate-100 text-slate-500'
                            }`}>
                              {p.status}
                            </span>
                            {selectedProjectId === p.id && <Check size={16} className="text-primary-600" />}
                          </div>
                        </button>
                      ))
                    )}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* Project Info */}
            {selectedProject && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                className="flex flex-col gap-3 pt-3 border-t border-slate-100"
              >
                <div className="grid grid-cols-2 gap-3">
                  <div className="bg-slate-50 rounded-lg px-3 py-2">
                    <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Type</div>
                    <div className="text-sm font-bold text-slate-700 mt-0.5">{selectedProject.disclosure_type}</div>
                  </div>
                  <div className="bg-slate-50 rounded-lg px-3 py-2">
                    <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Status</div>
                    <div className={`text-sm font-bold mt-0.5 ${
                      selectedProject.status === 'Completed' ? 'text-emerald-600' :
                      selectedProject.status === 'Validating' ? 'text-amber-600' : 'text-slate-700'
                    }`}>
                      {selectedProject.status}
                    </div>
                  </div>
                  <div className="bg-slate-50 rounded-lg px-3 py-2">
                    <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Documents</div>
                    <div className="text-sm font-bold text-slate-700 mt-0.5">{selectedProject.document_count}</div>
                  </div>
                  <div className="bg-slate-50 rounded-lg px-3 py-2">
                    <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Progress</div>
                    <div className="text-sm font-bold text-primary-600 mt-0.5">{selectedProject.progress}%</div>
                  </div>
                </div>
                <div className="text-xs text-slate-400 font-medium">
                  Period: {selectedProject.reporting_period_start} → {selectedProject.reporting_period_end}
                </div>
              </motion.div>
            )}

            {/* What's Included */}
            <div className="flex flex-col gap-2 pt-3 border-t border-slate-100">
              <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-1">Package Includes</div>
              {[
                { icon: BookOpen, label: 'Executive disclosure summary table' },
                { icon: FileText, label: 'Detailed field-by-field narratives' },
                { icon: Shield, label: 'Evidence citations & audit quotes' },
                { icon: CheckCircle, label: 'Reviewer sign-off sections' },
              ].map((item, i) => (
                <div key={i} className="flex items-center gap-2.5 text-xs text-slate-600 font-medium">
                  <div className="w-5 h-5 rounded-md bg-violet-50 flex items-center justify-center shrink-0">
                    <item.icon size={12} className="text-violet-500" />
                  </div>
                  {item.label}
                </div>
              ))}
            </div>
          </div>
        </motion.div>

        {/* Right: Preview + Download Area */}
        <motion.div variants={itemVariants} className="lg:col-span-2">
          <div className="glass-card overflow-hidden flex flex-col h-full">
            {/* Toolbar */}
            <div className="flex items-center justify-between px-5 py-3 border-b border-slate-100 bg-slate-50/50">
              <div className="flex items-center gap-1 bg-white border border-slate-200 rounded-xl p-1 shadow-sm">
                <button
                  onClick={() => setActiveTab('markdown')}
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold transition-all ${
                    activeTab === 'markdown'
                      ? 'bg-gradient-to-r from-primary-500 to-primary-600 text-white shadow-md shadow-primary-500/20'
                      : 'text-slate-500 hover:text-slate-700 hover:bg-slate-50'
                  }`}
                >
                  <FileText size={14} />
                  Markdown
                </button>
                <button
                  onClick={() => setActiveTab('html')}
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold transition-all ${
                    activeTab === 'html'
                      ? 'bg-gradient-to-r from-violet-500 to-indigo-600 text-white shadow-md shadow-violet-500/20'
                      : 'text-slate-500 hover:text-slate-700 hover:bg-slate-50'
                  }`}
                >
                  <Code2 size={14} />
                  HTML Report
                </button>
              </div>

              <div className="flex items-center gap-2">
                {activeTab === 'html' && htmlContent && (
                  <button
                    onClick={() => setShowPreview(!showPreview)}
                    className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-bold text-slate-500 hover:text-slate-700 hover:bg-white border border-transparent hover:border-slate-200 transition-all"
                    title={showPreview ? 'Show raw HTML' : 'Show rendered preview'}
                  >
                    {showPreview ? <EyeOff size={14} /> : <Eye size={14} />}
                    {showPreview ? 'Raw' : 'Preview'}
                  </button>
                )}

                <button
                  onClick={handleRefresh}
                  disabled={!selectedProjectId || isCurrentLoading}
                  className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-bold text-slate-500 hover:text-slate-700 hover:bg-white border border-transparent hover:border-slate-200 transition-all disabled:opacity-40"
                  title="Refresh export"
                >
                  <RefreshCw size={14} className={isCurrentLoading ? 'animate-spin' : ''} />
                </button>

                <button
                  onClick={handleCopy}
                  disabled={!currentContent}
                  className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-bold text-slate-500 hover:text-slate-700 hover:bg-white border border-transparent hover:border-slate-200 transition-all disabled:opacity-40"
                  title="Copy to clipboard"
                >
                  {copied ? <CheckCircle size={14} className="text-emerald-500" /> : <Copy size={14} />}
                  {copied ? 'Copied!' : 'Copy'}
                </button>

                {activeTab === 'html' && htmlContent && (
                  <button
                    onClick={handlePrint}
                    className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-bold text-slate-500 hover:text-slate-700 hover:bg-white border border-transparent hover:border-slate-200 transition-all"
                    title="Print HTML report"
                  >
                    <Printer size={14} />
                    Print
                  </button>
                )}
              </div>
            </div>

            {/* Content Area */}
            <div className="flex-1 min-h-[500px] relative overflow-hidden">
              {!selectedProjectId ? (
                <div className="flex flex-col items-center justify-center h-full py-20 gap-4 text-center px-8">
                  <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-violet-100 to-indigo-100 flex items-center justify-center mb-2">
                    <Package size={36} className="text-violet-400" />
                  </div>
                  <h3 className="text-lg font-bold text-slate-700">Select a Project to Generate Exports</h3>
                  <p className="text-sm text-slate-400 font-medium max-w-sm">
                    Choose a reporting project from the left panel to generate audit-ready Markdown and HTML disclosure packages with evidence citations.
                  </p>
                  <div className="flex items-center gap-2 text-xs font-bold text-violet-500 mt-2">
                    <ArrowRight size={14} />
                    Pick a project to get started
                  </div>
                </div>
              ) : isCurrentLoading ? (
                <div className="flex flex-col items-center justify-center h-full py-20 gap-4">
                  <div className="relative">
                    <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-violet-100 to-indigo-100 flex items-center justify-center">
                      <Loader size={28} className="animate-spin text-violet-500" />
                    </div>
                    <div className="absolute -top-1 -right-1 w-6 h-6 bg-violet-500 rounded-lg flex items-center justify-center shadow-lg shadow-violet-500/30">
                      <Sparkles size={12} className="text-white" />
                    </div>
                  </div>
                  <div className="text-sm font-bold text-slate-600">Generating {activeTab === 'markdown' ? 'Markdown' : 'HTML'} package...</div>
                  <div className="text-xs text-slate-400 font-medium">Compiling evidence citations, draft narratives, and sign-off sections</div>
                </div>
              ) : error ? (
                <div className="flex flex-col items-center justify-center h-full py-20 gap-4 text-center px-8">
                  <div className="w-16 h-16 rounded-2xl bg-rose-50 flex items-center justify-center">
                    <AlertTriangle size={28} className="text-rose-400" />
                  </div>
                  <h3 className="text-sm font-bold text-rose-600">{error}</h3>
                  <p className="text-xs text-slate-400 font-medium max-w-sm">
                    Ensure the project has uploaded documents and has been processed with AI extraction before exporting.
                  </p>
                  <button
                    onClick={handleRefresh}
                    className="mt-2 px-4 py-2 bg-white border border-slate-200 rounded-xl text-xs font-bold text-slate-600 hover:border-primary-300 hover:text-primary-600 transition-all"
                  >
                    Try Again
                  </button>
                </div>
              ) : currentContent ? (
                <div className="h-full overflow-auto">
                  {activeTab === 'markdown' ? (
                    <pre className="p-6 text-xs leading-relaxed text-slate-700 font-mono whitespace-pre-wrap bg-slate-50/50 min-h-full selection:bg-violet-200 selection:text-violet-900">
                      {markdownContent}
                    </pre>
                  ) : showPreview ? (
                    <iframe
                      ref={htmlPreviewRef}
                      srcDoc={htmlContent}
                      className="w-full h-full min-h-[500px] border-0"
                      title="HTML Report Preview"
                      sandbox="allow-same-origin"
                    />
                  ) : (
                    <pre className="p-6 text-xs leading-relaxed text-slate-700 font-mono whitespace-pre-wrap bg-slate-50/50 min-h-full selection:bg-violet-200 selection:text-violet-900">
                      {htmlContent}
                    </pre>
                  )}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center h-full py-20 gap-3 text-center">
                  <div className="text-sm text-slate-400 font-medium">No content generated yet</div>
                </div>
              )}
            </div>

            {/* Download Bar */}
            {currentContent && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex items-center justify-between px-5 py-4 border-t border-slate-100 bg-gradient-to-r from-slate-50 to-violet-50/30"
              >
                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-1.5">
                    <CheckCircle size={14} className="text-emerald-500" />
                    <span className="text-xs font-bold text-emerald-600">Package ready</span>
                  </div>
                  <span className="text-xs text-slate-400 font-medium">
                    {(new Blob([currentContent]).size / 1024).toFixed(1)} KB · {currentContent.split('\n').length} lines
                  </span>
                </div>

                <div className="flex items-center gap-3">
                  <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={() => handleDownload('markdown')}
                    disabled={!markdownContent}
                    className="flex items-center gap-2 px-4 py-2.5 bg-white border border-slate-200 rounded-xl text-xs font-bold text-slate-700 hover:border-primary-300 hover:text-primary-600 hover:shadow-md transition-all disabled:opacity-40 disabled:hover:border-slate-200 disabled:hover:text-slate-700"
                  >
                    <FileText size={14} />
                    Download .md
                  </motion.button>
                  <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={() => handleDownload('html')}
                    disabled={!htmlContent}
                    className="flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-violet-500 to-indigo-600 text-white rounded-xl text-xs font-bold shadow-lg shadow-violet-500/20 hover:shadow-xl hover:shadow-violet-500/30 transition-all disabled:opacity-40"
                  >
                    <Download size={14} />
                    Download .html
                  </motion.button>
                </div>
              </motion.div>
            )}
          </div>
        </motion.div>
      </motion.div>
    </div>
  );
};

export default AuditExport;
