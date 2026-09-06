import '@testing-library/jest-dom'
import React from 'react'

jest.mock('react-syntax-highlighter', () => ({
	Prism: ({ children }) => React.createElement('pre', null, children),
}))

jest.mock('react-syntax-highlighter/dist/esm/styles/prism', () => ({
	vscDarkPlus: {},
}))
