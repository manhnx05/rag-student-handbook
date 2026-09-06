import type { Citation } from '@/types/rag';

export function CitationList({ citations }: { citations: Citation[] }) {
  if (citations.length === 0) return null;

  return (
    <aside aria-label="Nguồn tham khảo" className="space-y-2 border-t pt-3 text-sm">
      <h3 className="font-medium">Nguồn tham khảo</h3>
      <ol className="space-y-1 text-muted-foreground">
        {citations.map((citation) => (
          <li key={`${citation.source}-${citation.page ?? 'unknown'}`}>
            [{citation.id}] {citation.source}
            {citation.page ? `, trang ${citation.page}` : ''}
          </li>
        ))}
      </ol>
    </aside>
  );
}
