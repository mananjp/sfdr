import React, { createContext, useContext, useState, useEffect } from 'react';
import client from '../api/client';
import { useAuth } from './AuthContext';

const ProjectContext = createContext();

export const useProjects = () => useContext(ProjectContext);

export const ProjectProvider = ({ children }) => {
  const { currentUser } = useAuth();
  const [projects, setProjects] = useState([]);
  const [selectedProjectId, setSelectedProjectId] = useState(localStorage.getItem('clarix_selected_project') || null);
  const [isLoadingProjects, setIsLoadingProjects] = useState(true);

  const fetchProjects = async () => {
    setIsLoadingProjects(true);
    try {
      const response = await client.get('/projects');
      if (Array.isArray(response.data)) {
        setProjects(response.data);

        // If we have a stored ID but it's not in the new projects list, clear it
        if (selectedProjectId && !response.data.some(p => p.id === selectedProjectId)) {
          if (response.data.length > 0) {
            selectProject(response.data[0].id);
          } else {
            selectProject(null);
          }
        } else if (!selectedProjectId && response.data.length > 0) {
          // Auto-select first if none selected
          selectProject(response.data[0].id);
        }
      } else {
        console.error("Projects API did not return an array. Check if VITE_API_URL is configured correctly. Received:", response.data);
        setProjects([]);
      }
    } catch (error) {
      console.error("Failed to load projects", error);
    } finally {
      setIsLoadingProjects(false);
    }
  };

  const selectProject = (id) => {
    setSelectedProjectId(id);
    if (id) {
      localStorage.setItem('clarix_selected_project', id);
    } else {
      localStorage.removeItem('clarix_selected_project');
    }
  };

  // Only fetch if a user is logged in
  useEffect(() => {
    if (currentUser) {
      fetchProjects();
    } else {
      setProjects([]);
      setSelectedProjectId(null);
      localStorage.removeItem('clarix_selected_project');
      setIsLoadingProjects(false);
    }
  }, [currentUser]);

  const value = {
    projects,
    selectedProjectId,
    selectProject,
    isLoadingProjects,
    fetchProjects
  };

  return <ProjectContext.Provider value={value}>{children}</ProjectContext.Provider>;
};
