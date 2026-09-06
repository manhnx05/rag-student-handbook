import Link from 'next/link';
import { Network } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

export default function GraphPage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-4xl items-center px-6 py-12">
      <Card className="w-full">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Network className="h-5 w-5" />
            Knowledge graph
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 text-sm text-muted-foreground">
          <p>Neo4j đang cung cấp entity và relationship context cho hybrid retrieval.</p>
          <p>Giao diện trực quan hóa graph sẽ hiển thị sau khi có graph query endpoint.</p>
          <Link className="text-primary underline" href="/chat">Quay lại trợ lý</Link>
        </CardContent>
      </Card>
    </main>
  );
}
