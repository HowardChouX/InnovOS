import { createContext, use } from 'react';
import type { RecallTestContextValue } from './types';

export const RecallTestContext = createContext<RecallTestContextValue | null>(null);

export const useRecallTest = () => {
  const context = use(RecallTestContext);
  if (!context) {
    throw new Error('RecallTest components must be used within RecallTestProvider');
  }
  return context;
};
