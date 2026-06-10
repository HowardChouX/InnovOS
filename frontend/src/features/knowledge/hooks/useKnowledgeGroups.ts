import { useState, useEffect, useCallback } from 'react';
import { knowledgeApi } from '../../../api/knowledge';
import type { KnowledgeGroup } from '../../../types/knowledge';
import { normalizeKnowledgeError } from '../utils';

/**
 * Hook for listing knowledge groups.
 */
export const useKnowledgeGroups = () => {
  const [groups, setGroups] = useState<KnowledgeGroup[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const refetch = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await knowledgeApi.listGroups();
      setGroups(res.data || []);
    } catch (err) {
      const normalized = normalizeKnowledgeError(err);
      setError(normalized);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    refetch();
  }, [refetch]);

  return { groups, isLoading, error, refetch };
};

/**
 * Hook for creating a knowledge group.
 */
export const useCreateKnowledgeGroup = () => {
  const [isCreating, setIsCreating] = useState(false);
  const [createError, setCreateError] = useState<Error | null>(null);

  const createGroup = useCallback(async (name: string): Promise<KnowledgeGroup> => {
    const normalizedName = name.trim();
    if (!normalizedName) {
      throw new Error('知识分组名称不能为空');
    }

    setIsCreating(true);
    setCreateError(null);

    try {
      const res = await knowledgeApi.createGroup(normalizedName);
      return res.data;
    } catch (err) {
      const normalized = normalizeKnowledgeError(err);
      setCreateError(normalized);
      throw normalized;
    } finally {
      setIsCreating(false);
    }
  }, []);

  return { createGroup, isCreating, createError };
};

/**
 * Hook for updating a knowledge group.
 */
export const useUpdateKnowledgeGroup = () => {
  const [isUpdating, setIsUpdating] = useState(false);
  const [updateError, setUpdateError] = useState<Error | null>(null);

  const updateGroup = useCallback(async (groupId: string, updates: { name: string }) => {
    setIsUpdating(true);
    setUpdateError(null);

    try {
      const res = await knowledgeApi.updateGroup(groupId, updates);
      return res.data;
    } catch (err) {
      const normalized = normalizeKnowledgeError(err);
      setUpdateError(normalized);
      throw normalized;
    } finally {
      setIsUpdating(false);
    }
  }, []);

  return { updateGroup, isUpdating, updateError };
};

/**
 * Hook for deleting a knowledge group.
 */
export const useDeleteKnowledgeGroup = () => {
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<Error | null>(null);

  const deleteGroup = useCallback(async (groupId: string) => {
    setIsDeleting(true);
    setDeleteError(null);

    try {
      await knowledgeApi.deleteGroup(groupId);
    } catch (err) {
      const normalized = normalizeKnowledgeError(err);
      setDeleteError(normalized);
      throw normalized;
    } finally {
      setIsDeleting(false);
    }
  }, []);

  return { deleteGroup, isDeleting, deleteError };
};
