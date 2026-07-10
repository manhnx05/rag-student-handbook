import { render, screen } from '@testing-library/react'
import { MessageBubble } from '@/components/chat/MessageBubble'

// Mock react-markdown because it uses ESM which Jest struggles with out-of-the-box
jest.mock('react-markdown', () => (props: { children: string }) => <div data-testid="react-markdown">{props.children}</div>)

describe('MessageBubble', () => {
  it('renders user message correctly', () => {
    render(<MessageBubble role="user" content="How much is the fee?" />)
    expect(screen.getByText('You')).toBeInTheDocument()
    expect(screen.getByText('How much is the fee?')).toBeInTheDocument()
    expect(screen.getByText('U')).toBeInTheDocument()
  })

  it('renders assistant message correctly', () => {
    render(<MessageBubble role="assistant" content="The fee is 500$." />)
    expect(screen.getByText('Handbook Assistant')).toBeInTheDocument()
    expect(screen.getByText('The fee is 500$.')).toBeInTheDocument()
    expect(screen.getByText('AI')).toBeInTheDocument()
  })
})
