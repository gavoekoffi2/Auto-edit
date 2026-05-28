import { InputHTMLAttributes, useId } from 'react'

interface Props extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
}

export default function Input({ label, error, className = '', id: propId, ...props }: Props) {
  const generatedId = useId()
  const inputId = propId || generatedId
  const errorId = error ? `${inputId}-error` : undefined

  return (
    <div>
      {label && (
        <label htmlFor={inputId} className="block text-sm font-medium text-dark-300 mb-1">{label}</label>
      )}
      <input
        id={inputId}
        aria-invalid={error ? true : undefined}
        aria-describedby={errorId}
        className={`input-field ${error ? 'border-red-500' : ''} ${className}`}
        {...props}
      />
      {error && <p id={errorId} className="text-red-400 text-sm mt-1" role="alert">{error}</p>}
    </div>
  )
}
