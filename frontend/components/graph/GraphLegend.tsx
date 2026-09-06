const entries = [
  { label: 'Entity', color: 'bg-blue-500' },
  { label: 'Rule', color: 'bg-amber-500' },
  { label: 'Organization', color: 'bg-emerald-500' },
];

export function GraphLegend() {
  return (
    <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
      {entries.map((entry) => (
        <span key={entry.label} className="flex items-center gap-2">
          <span className={`h-2.5 w-2.5 rounded-full ${entry.color}`} />
          {entry.label}
        </span>
      ))}
    </div>
  );
}
