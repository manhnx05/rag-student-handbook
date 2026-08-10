import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Plus, MessageSquare, LogOut } from "lucide-react";
import { cn } from "@/lib/utils";
import { ChatSession } from "../hooks/useChatStream";

interface ChatSidebarProps {
  sessions: ChatSession[];
  activeSessionId: string | null;
  sidebarOpen: boolean;
  user: { email: string } | null;
  onSelectSession: (id: string) => void;
  onNewChat: () => void;
  onLogout: () => void;
}

export function ChatSidebar({
  sessions,
  activeSessionId,
  sidebarOpen,
  user,
  onSelectSession,
  onNewChat,
  onLogout
}: ChatSidebarProps) {
  return (
    <div
      className={cn(
        "fixed inset-y-0 left-0 z-50 w-64 bg-gray-900 text-white transition-transform duration-300 ease-in-out md:relative",
        sidebarOpen ? "translate-x-0" : "-translate-x-full hidden md:flex"
      )}
    >
      <div className="flex flex-col h-full w-full">
        <div className="p-4 flex items-center justify-between">
          <Button
            variant="ghost"
            className="w-full justify-start gap-2 hover:bg-gray-800 text-white"
            onClick={onNewChat}
          >
            <Plus className="w-5 h-5" />
            New Chat
          </Button>
        </div>
        <ScrollArea className="flex-1 px-2">
          <div className="space-y-2">
            {sessions.map((session) => (
              <button
                key={session.id}
                onClick={() => onSelectSession(session.id)}
                className={cn(
                  "flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm text-left transition-colors",
                  activeSessionId === session.id
                    ? "bg-gray-800 text-white"
                    : "text-gray-400 hover:bg-gray-800 hover:text-white"
                )}
              >
                <MessageSquare className="w-4 h-4 shrink-0" />
                <span className="truncate">{session.title}</span>
              </button>
            ))}
          </div>
        </ScrollArea>
        {user && (
          <div className="p-4 border-t border-gray-800">
            <div className="flex items-center gap-3 mb-4">
              <Avatar className="w-8 h-8">
                <AvatarFallback>{user.email[0].toUpperCase()}</AvatarFallback>
              </Avatar>
              <div className="text-sm truncate max-w-[150px]">{user.email}</div>
            </div>
            <Button
              variant="ghost"
              className="w-full justify-start gap-2 hover:bg-gray-800 text-red-400 hover:text-red-300"
              onClick={onLogout}
            >
              <LogOut className="w-5 h-5" />
              Log out
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
