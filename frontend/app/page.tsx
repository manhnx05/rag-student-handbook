
'use client'

import { useState } from 'react'
import axios from 'axios'

export default function Home() {
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    try {
      const response = await axios.post('http://localhost:8000/api/chat', {
        question
      })
      setAnswer(response.data.answer)
    } catch (error) {
      console.error(error)
      setAnswer('Có lỗi xảy ra, vui lòng thử lại sau.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="container mx-auto p-4">
      <h1 className="text-2xl font-bold mb-4">Medi-Chatbot</h1>
      <form onSubmit={handleSubmit} className="flex flex-col gap-2">
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Nhập câu hỏi của bạn..."
          className="p-2 border rounded"
          disabled={loading}
        />
        <button
          type="submit"
          className="p-2 bg-blue-500 text-white rounded hover:bg-blue-600"
          disabled={loading}
        >
          {loading ? 'Đang xử lý...' : 'Gửi'}
        </button>
      </form>
      {answer && (
        <div className="mt-4 p-4 border rounded bg-gray-50">
          <h3 className="font-semibold mb-2">Trả lời:</h3>
          <p>{answer}</p>
        </div>
      )}
    </div>
  )
}
