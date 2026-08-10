import React from 'react';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { motion } from 'framer-motion';
import { cn } from '@/lib/utils';
import { ChatMessage } from '../hooks/useChatStream';

export const MessageBubble = React.memo(({ msg }: { msg: ChatMessage }) => {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className={cn(
        "flex gap-4 w-full",
        msg.role === 'user' ? "justify-end" : "justify-start"
      )}
    >
      {msg.role === 'ai' && (
        <Avatar className="w-8 h-8 mt-1 shrink-0 bg-blue-600">
          <AvatarFallback className="text-white">AI</AvatarFallback>
        </Avatar>
      )}
      <div
        className={cn(
          "px-4 py-3 rounded-2xl max-w-[85%]",
          msg.role === 'user'
            ? "bg-blue-600 text-white rounded-tr-sm"
            : "bg-white dark:bg-gray-800 shadow-sm border rounded-tl-sm text-gray-800 dark:text-gray-200"
        )}
      >
        {msg.role === 'user' ? (
          <p className="whitespace-pre-wrap">{msg.content}</p>
        ) : (
          <div className="prose prose-sm max-w-none dark:prose-invert">
            {msg.content ? (
              <ReactMarkdown
                components={{
                  code({node, inline, className, children, ...props}: any) {
                    const match = /language-(\w+)/.exec(className || '')
                    return !inline && match ? (
                      <SyntaxHighlighter
                        {...props}
                        style={vscDarkPlus as any}
                        language={match[1]}
                        PreTag="div"
                      >
                        {String(children).replace(/\n$/, '')}
                      </SyntaxHighlighter>
                    ) : (
                      <code {...props} className={cn("bg-gray-100 dark:bg-gray-700 rounded px-1 py-0.5", className)}>
                        {children}
                      </code>
                    )
                  }
                }}
              >
                {msg.content}
              </ReactMarkdown>
            ) : (
              <span className="flex items-center gap-1 h-6">
                <motion.span 
                  animate={{ y: [0, -4, 0] }} 
                  transition={{ repeat: Infinity, duration: 0.6, delay: 0 }} 
                  className="w-2 h-2 bg-gray-400 rounded-full"
                />
                <motion.span 
                  animate={{ y: [0, -4, 0] }} 
                  transition={{ repeat: Infinity, duration: 0.6, delay: 0.2 }} 
                  className="w-2 h-2 bg-gray-400 rounded-full"
                />
                <motion.span 
                  animate={{ y: [0, -4, 0] }} 
                  transition={{ repeat: Infinity, duration: 0.6, delay: 0.4 }} 
                  className="w-2 h-2 bg-gray-400 rounded-full"
                />
              </span>
            )}
          </div>
        )}
      </div>
    </motion.div>
  );
});

MessageBubble.displayName = 'MessageBubble';
