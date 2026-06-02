import { ButtonHTMLAttributes } from 'react'
import { Loader2 } from 'lucide-react'

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'accent'
  loading?: boolean
}

const variants = {
  primary: 'btn-primary',
  secondary: 'btn-secondary',
  accent: 'btn-accent',
}

export default function Button({ variant = 'primary', loading, children, disabled, className = '', ...props }: Props) {
  return (
    <button
      className={`${variants[variant]} ${className} inline-flex items-center justify-center gap-2 disabled:opacity-50`}
      disabled={disabled || loading}
      {...props}
    >
      {loading && <Loader2 className="w-4 h-4 animate-spin" />}
      {children}
    </button>
  )
}
