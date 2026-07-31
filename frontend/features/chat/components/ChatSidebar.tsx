import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { PlusCircle, MessageSquare, Settings } from "lucide-react"

export function ChatSidebar() {
  return (
    <div className="w-64 border-r bg-gray-50/50 dark:bg-gray-900/50 flex flex-col h-screen">
      <div className="p-4 border-b">
        <Button className="w-full flex items-center gap-2" variant="default">
          <PlusCircle className="w-4 h-4" />
          New Chat
        </Button>
      </div>
      <ScrollArea className="flex-1 p-4">
        <div className="space-y-2">
          {/* Mock history */}
          <Button variant="ghost" className="w-full justify-start gap-2">
            <MessageSquare className="w-4 h-4" />
            <span className="truncate">Quy chế đào tạo 2024</span>
          </Button>
          <Button variant="ghost" className="w-full justify-start gap-2">
            <MessageSquare className="w-4 h-4" />
            <span className="truncate">Học phí kỳ 1</span>
          </Button>
        </div>
      </ScrollArea>
      <div className="p-4 border-t mt-auto">
        <Button variant="ghost" className="w-full justify-start gap-2">
          <Settings className="w-4 h-4" />
          Settings
        </Button>
      </div>
    </div>
  )
}
