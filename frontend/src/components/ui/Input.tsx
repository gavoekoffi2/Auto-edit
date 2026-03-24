import { InputHTMLAttributes } from 'react'

interface Props extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
}

export default function Input({ label, error, className = '', ...props }: Props) {
  return (
    <div>
      {label && (
        <label className="block text-sm font-medium text-dark-300 mb-1">{label}</label>
      )}
      <input className={`input-field ${error ? 'border-red-500' : ''} ${className}`} {...props} />
      {error && <p className="text-red-400 text-sm mt-1">{error}</p>}
    </div>
  )
}
