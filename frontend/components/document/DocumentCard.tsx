import { FileText } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';

export function DocumentCard({ name, pages }: { name: string; pages?: number }) {
  return (
    <Card>
      <CardContent className="flex items-center gap-3 p-4">
        <FileText className="h-5 w-5 text-muted-foreground" />
        <div>
          <p className="font-medium">{name}</p>
          {pages !== undefined && <p className="text-sm text-muted-foreground">{pages} trang</p>}
        </div>
      </CardContent>
    </Card>
  );
}
