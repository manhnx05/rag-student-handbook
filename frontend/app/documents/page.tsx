'use client';

import { useState } from 'react';
import { FileUp } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import api from '@/lib/api';

export default function DocumentsPage() {
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState('');
  const [isUploading, setIsUploading] = useState(false);

  const handleUpload = async () => {
    if (!file) return;
    setIsUploading(true);
    setStatus('');
    try {
      const formData = new FormData();
      formData.append('file', file);
      await api.post('/ingest', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setStatus(`Đã gửi ${file.name} vào hàng đợi xử lý.`);
      setFile(null);
    } catch {
      setStatus('Không thể tải tài liệu. Hãy kiểm tra quyền admin và thử lại.');
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <main className="mx-auto flex min-h-screen max-w-4xl items-center px-6 py-12">
      <Card className="w-full">
        <CardHeader>
          <CardTitle>Quản lý tài liệu</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <label className="flex cursor-pointer flex-col items-center gap-3 rounded-lg border border-dashed p-10 text-center hover:bg-muted/40">
            <FileUp className="h-8 w-8 text-muted-foreground" />
            <span>{file?.name ?? 'Chọn tài liệu PDF để ingest'}</span>
            <input
              type="file"
              accept="application/pdf,.pdf"
              className="sr-only"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            />
          </label>
          <Button onClick={handleUpload} disabled={!file || isUploading}>
            {isUploading ? 'Đang tải...' : 'Bắt đầu ingest'}
          </Button>
          {status && <p className="text-sm text-muted-foreground">{status}</p>}
        </CardContent>
      </Card>
    </main>
  );
}
