import { knowledgeApi } from './knowledge';

export interface UploadResult {
  id?: string;
  name: string;
  size: number;
  error?: string;
}

/**
 * Upload a file using presigned URL (browser → S3), with fallback to direct upload.
 * Returns the upload result or throws on failure.
 */
export async function uploadFileWithFallback(file: File, baseId?: string): Promise<UploadResult> {
  // Step 1: Try presigned URL
  const uploadInfo = await knowledgeApi.getUploadUrl(file.name, baseId, file.type);

  if (uploadInfo) {
    // Step 2: PUT file directly to S3
    const putRes = await fetch(uploadInfo.uploadUrl, {
      method: 'PUT',
      body: file,
      headers: { 'Content-Type': file.type },
    });
    if (!putRes.ok) {
      throw new Error(`S3 上传失败 (${putRes.status})`);
    }

    // Step 3: Confirm upload to backend
    const confirmRes = await knowledgeApi.confirmUpload({
      baseId: baseId || '',
      itemId: uploadInfo.itemId,
      objectKey: uploadInfo.objectKey,
      filename: file.name,
    });

    return {
      id: confirmRes.data.id,
      name: file.name,
      size: file.size,
    };
  }

  // Fallback: direct HTTP upload
  const res = await knowledgeApi.uploadFile(file, baseId);
  return {
    id: res.data?.id || '',
    name: file.name,
    size: file.size,
  };
}
