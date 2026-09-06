import { render, screen, act } from '@testing-library/react'
import { ChatSidebar } from '@/components/chat/ChatSidebar'

describe('ChatSidebar', () => {
  it('renders sidebar buttons', async () => {
    const mockProps = {
      sessions: [{ id: '1', title: 'Quy chế đào tạo 2024', created_at: new Date().toISOString() }],
      activeSessionId: null,
      sidebarOpen: true,
      user: { email: 'test@example.com' },
      onSelectSession: jest.fn(),
      onNewChat: jest.fn(),
      onDeleteSession: jest.fn(),
      onLogout: jest.fn(),
    };

    await act(async () => {
      render(<ChatSidebar {...mockProps} />)
    })
    expect(screen.getByText('New Chat')).toBeInTheDocument()
    expect(screen.getByText('Quy chế đào tạo 2024')).toBeInTheDocument()
    expect(screen.getByText('test@example.com')).toBeInTheDocument()
    expect(screen.getByText('Log out')).toBeInTheDocument()
  })
})
