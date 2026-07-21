/**
 * @fileoverview 설정 사이드바 상태 store
 */
import { create } from 'zustand';

type SettingSidebarStoreState = {
  isOpenSidebar: boolean;
  toggleSidebar: () => void;
  closeSidebar: () => void;
};

const useSettingSidebarStore = create<SettingSidebarStoreState>((set) => ({
  isOpenSidebar: false,
  toggleSidebar: () => set((state) => ({ isOpenSidebar: !state.isOpenSidebar })),
  closeSidebar: () => set(() => ({ isOpenSidebar: false })),
}));

export default useSettingSidebarStore;
