import { useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import type { KnowledgeItem, KnowledgeItemChunk } from '../../../types/knowledge';
import { normalizeKnowledgeError, getErrorMessage } from '../utils';

/**
 * Hook for previewing a knowledge source item.
 *
 * - For URL/note items, opens the URL in a new browser tab.
 * - Provides a `previewSource(item)` function and optional chunk preview data.
 */
export const usePreviewKnowledgeSource = () => {
  const { t } = useTranslation();
  const [previewData] = useState<KnowledgeItemChunk[] | null>(null);

  const previewSource = useCallback(
    async (item: KnowledgeItem): Promise<void> => {
      const source = item.data.source?.trim();

      if (!source) {
        alert(t('knowledge.data_source.preview.unavailable'));
        return;
      }

      try {
        if (item.type === 'url' || item.type === 'note') {
          let previewUrl: string | null = null;

          if (item.type === 'url') {
            previewUrl = source;
          } else if (item.type === 'note') {
            previewUrl = (item.data as { sourceUrl?: string }).sourceUrl || source;
          }

          if (previewUrl && (previewUrl.startsWith('http://') || previewUrl.startsWith('https://'))) {
            window.open(previewUrl, '_blank', 'noopener,noreferrer');
            return;
          }

          alert(t('knowledge.data_source.preview.unavailable'));
          return;
        }

        // For file/directory types, local file preview is unavailable in a web app
        alert(t('knowledge.data_source.preview.unavailable'));
      } catch (error) {
        const previewError = normalizeKnowledgeError(error);
        alert(`${t('knowledge.data_source.preview.failed')}: ${getErrorMessage(previewError)}`);
      }
    },
    [t]
  );

  return {
    previewSource,
    previewData,
  };
};
