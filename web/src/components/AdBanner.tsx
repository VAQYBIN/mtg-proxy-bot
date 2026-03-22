import { Megaphone } from 'lucide-react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { cn } from '@/lib/utils'

interface AdBannerProps {
  url: string
  text: string
  buttonText: string
}

export function AdBanner({ url, text, buttonText }: AdBannerProps) {
  return (
    <Alert className="border-blue-200 bg-blue-50 text-blue-900 dark:border-blue-800 dark:bg-blue-950 dark:text-blue-100">
      <Megaphone className="size-4 text-blue-600 dark:text-blue-400" />
      {text && <AlertTitle>{text}</AlertTitle>}
      <AlertDescription>
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className={cn(
            'mt-1 inline-flex items-center rounded-lg border px-2.5 py-1 text-[0.8rem] font-medium transition-colors',
            'border-blue-300 bg-white text-blue-800 hover:bg-blue-100',
            'dark:border-blue-700 dark:bg-blue-900 dark:text-blue-100 dark:hover:bg-blue-800',
          )}
        >
          {buttonText}
        </a>
      </AlertDescription>
    </Alert>
  )
}
