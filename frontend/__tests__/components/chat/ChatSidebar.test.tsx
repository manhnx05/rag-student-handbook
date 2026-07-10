import { render, screen } from '@testing-library/react'
import { ChatSidebar } from '@/components/chat/ChatSidebar'

describe('ChatSidebar', () => {
  it('renders sidebar buttons', () => {
    render(<ChatSidebar />)
    expect(screen.getByText('New Chat')).toBeInTheDocument()
    expect(screen.getByText('Quy chế đào tạo 2024')).toBeInTheDocument()
    expect(screen.getByText('Settings')).toBeInTheDocument()
  })
})
