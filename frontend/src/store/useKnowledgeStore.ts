import { create } from 'zustand';
import { knowledgeApi } from '../api/knowledge';
import type { KnowledgeBase, KnowledgeBaseListItem, KnowledgeItem, KnowledgeGroup, KnowledgeTabKey } from '../types/knowledge';

interface KnowledgeStore {
  bases: KnowledgeBaseListItem[];
  groups: KnowledgeGroup[];
  selectedBaseId: string;
  selectedItemId: string | null;
  items: KnowledgeItem[];
  itemsTotal: number;
  itemsPage: number;
  tabCounts: Record<KnowledgeTabKey, number>;
  loading: boolean;
  activeTab: KnowledgeTabKey;
  searchQuery: string;
  isAddSourceOpen: boolean;
  isRagConfigOpen: boolean;
  isRecallTestOpen: boolean;
  isCreateBaseOpen: boolean;
  editingName: { id: string; name: string; type: 'base' | 'group' } | null;

  fetchBases: () => Promise<void>;
  fetchGroups: () => Promise<void>;
  selectBase: (id: string) => void;
  createBase: (name: string, groupId?: string, extra?: Record<string, any>) => Promise<void>;
  updateBase: (id: string, data: Partial<KnowledgeBase>) => Promise<void>;
  deleteBase: (id: string) => Promise<void>;
  renameBase: (id: string, name: string) => Promise<void>;
  renameGroup: (id: string, name: string) => Promise<void>;
  fetchItems: (baseId?: string, page?: number) => Promise<void>;
  uploadFile: (file: File) => Promise<void>;
  addItem: (type: 'file' | 'url' | 'note' | 'directory', data: Record<string, any>) => Promise<void>;
  deleteItem: (id: string) => Promise<void>;
  setActiveTab: (tab: KnowledgeTabKey) => void;
  setSearchQuery: (q: string) => void;
  openItemChunks: (id: string) => void;
  closeItemChunks: () => void;
  openAddSource: () => void;
  closeAddSource: () => void;
  openRagConfig: () => void;
  closeRagConfig: () => void;
  openRecallTest: () => void;
  closeRecallTest: () => void;
  openCreateBase: (groupId?: string) => void;
  closeCreateBase: () => void;
  openRename: (id: string, name: string, type: 'base' | 'group') => void;
  closeRename: () => void;
}

export const useKnowledgeStore = create<KnowledgeStore>((set, get) => ({
  bases: [],
  groups: [],
  selectedBaseId: '',
  selectedItemId: null,
  items: [],
  itemsTotal: 0,
  itemsPage: 1,
  tabCounts: { file: 0, note: 0, directory: 0, url: 0, website: 0 },
  loading: false,
  activeTab: 'file',
  searchQuery: '',
  isAddSourceOpen: false,
  isRagConfigOpen: false,
  isRecallTestOpen: false,
  isCreateBaseOpen: false,
  editingName: null,

  fetchBases: async () => {
    set({ loading: true });
    try {
      const res = await knowledgeApi.listBases();
      const bases = res.data?.items || [];
      set({ bases });
      if (bases.length > 0 && !get().selectedBaseId) {
        set({ selectedBaseId: bases[0].id });
        await get().fetchItems(bases[0].id);
      }
    } catch {
      set({ bases: [] });
    } finally {
      set({ loading: false });
    }
  },

  fetchGroups: async () => {
    try {
      const res = await knowledgeApi.listGroups();
      set({ groups: res.data || [] });
    } catch {
      set({ groups: [] });
    }
  },

  selectBase: (id) => {
    set({ selectedBaseId: id, selectedItemId: null, activeTab: 'file', searchQuery: '', items: [] });
    if (id) get().fetchItems(id);
  },

  createBase: async (name, groupId, extra) => {
    await knowledgeApi.createBase({ name, groupId, ...extra });
    await get().fetchBases();
    await get().fetchGroups();
  },

  updateBase: async (id, data) => {
    const payload: Record<string, any> = {};
    if (data.name !== undefined) payload.name = data.name;
    if (data.groupId !== undefined) payload.groupId = data.groupId;
    if (data.rerankModelId !== undefined) payload.rerankModelId = data.rerankModelId;
    if (data.fileProcessorId !== undefined) payload.fileProcessorId = data.fileProcessorId;
    if (data.chunkSize !== undefined) payload.chunkSize = data.chunkSize;
    if (data.chunkOverlap !== undefined) payload.chunkOverlap = data.chunkOverlap;
    if (data.threshold !== undefined) payload.threshold = data.threshold;
    if (data.documentCount !== undefined) payload.documentCount = data.documentCount;
    if (data.searchMode !== undefined) payload.searchMode = data.searchMode;
    if (data.hybridAlpha !== undefined) payload.hybridAlpha = data.hybridAlpha;
    if (data.status !== undefined) payload.status = data.status;
    if (data.error !== undefined) payload.error = data.error;
    if (data.dimensions !== undefined) payload.dimensions = data.dimensions;
    if (data.embeddingModelId !== undefined) payload.embeddingModelId = data.embeddingModelId;
    await knowledgeApi.updateBase(id, payload);
    await get().fetchBases();
  },

  deleteBase: async (id) => {
    await knowledgeApi.deleteBase(id);
    if (get().selectedBaseId === id) {
      set({ selectedBaseId: '', selectedItemId: null, items: [], itemsTotal: 0, tabCounts: { file: 0, note: 0, directory: 0, url: 0, website: 0 } });
    }
    await get().fetchBases();
  },

  renameBase: async (id, name) => {
    await knowledgeApi.updateBase(id, { name });
    await get().fetchBases();
  },

  renameGroup: async (_id, _name) => {
    await get().fetchGroups();
    await get().fetchBases();
  },

  fetchItems: async (baseId, page = 1) => {
    const bid = baseId || get().selectedBaseId;
    if (!bid) return;
    set({ loading: true });
    try {
      const type = get().activeTab === 'website' ? undefined : get().activeTab;
      const [filteredRes, allRes] = await Promise.all([
        knowledgeApi.listItems(bid, { page, limit: 20, type }),
        knowledgeApi.listItems(bid, { page: 1, limit: 9999, type: undefined }),
      ]);
      const allItems = allRes.data?.items || [];
      const counts: Record<KnowledgeTabKey, number> = { file: 0, note: 0, directory: 0, url: 0, website: 0 };
      for (const item of allItems) {
        if (item.type in counts) counts[item.type as KnowledgeTabKey]++;
      }
      set({
        items: filteredRes.data?.items || [],
        itemsTotal: filteredRes.data?.total || 0,
        itemsPage: filteredRes.data?.page || 1,
        tabCounts: counts,
      });
    } catch {
      set({ items: [], itemsTotal: 0, tabCounts: { file: 0, note: 0, directory: 0, url: 0, website: 0 } });
    } finally {
      set({ loading: false });
    }
  },

  uploadFile: async (file) => {
    const baseId = get().selectedBaseId;
    if (!baseId) return;
    await knowledgeApi.uploadFile(file, baseId);
    await get().fetchItems(baseId);
    await get().fetchBases();
  },

  addItem: async (type, data) => {
    const baseId = get().selectedBaseId;
    if (!baseId) return;
    await knowledgeApi.createItem(baseId, { type, data });
    await get().fetchItems(baseId);
    await get().fetchBases();
  },

  deleteItem: async (id) => {
    await knowledgeApi.deleteItem(id);
    const { selectedBaseId } = get();
    if (selectedBaseId) await get().fetchItems(selectedBaseId);
    await get().fetchBases();
  },

  setActiveTab: (tab) => {
    set({ activeTab: tab, selectedItemId: null });
    const { selectedBaseId } = get();
    if (selectedBaseId) get().fetchItems(selectedBaseId);
  },
  setSearchQuery: (q) => set({ searchQuery: q }),
  openItemChunks: (id) => set({ selectedItemId: id }),
  closeItemChunks: () => set({ selectedItemId: null }),
  openAddSource: () => set({ isAddSourceOpen: true }),
  closeAddSource: () => set({ isAddSourceOpen: false }),
  openRagConfig: () => set({ isRagConfigOpen: true }),
  closeRagConfig: () => set({ isRagConfigOpen: false }),
  openRecallTest: () => set({ isRecallTestOpen: true }),
  closeRecallTest: () => set({ isRecallTestOpen: false }),
  openCreateBase: () => set({ isCreateBaseOpen: true }),
  closeCreateBase: () => set({ isCreateBaseOpen: false }),
  openRename: (id, name, type) => set({ editingName: { id, name, type } }),
  closeRename: () => set({ editingName: null }),
}));
