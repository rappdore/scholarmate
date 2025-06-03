import axios from 'axios';
import type { EPUBDocument, EPUBDocumentInfo } from '../types/document';

const api = axios.create({
  baseURL: 'http://localhost:8000',
});

export const epubService = {
  listEPUBs: async (): Promise<EPUBDocument[]> => {
    const response = await api.get('/epub/list');
    return response.data;
  },

  getEPUBInfo: async (filename: string): Promise<EPUBDocumentInfo> => {
    const response = await api.get(`/epub/${filename}/info`);
    return response.data;
  },

  getEPUBFile: async (filename: string): Promise<any> => {
    // This will return 404 for now as per the plan
    const response = await api.get(`/epub/${filename}/file`);
    return response.data;
  },

  getThumbnailUrl: (filename: string): string => {
    return `http://localhost:8000/epub/${encodeURIComponent(filename)}/thumbnail`;
  },

  getNavigation: async (filename: string): Promise<any> => {
    const response = await api.get(
      `/epub/${encodeURIComponent(filename)}/navigation`
    );
    return response.data;
  },

  getContent: async (filename: string, navId: string): Promise<any> => {
    const response = await api.get(
      `/epub/${encodeURIComponent(filename)}/content/${encodeURIComponent(navId)}`
    );
    return response.data;
  },
};
