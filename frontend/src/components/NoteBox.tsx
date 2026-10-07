import { useLayoutEffect, useRef, type TextareaHTMLAttributes } from 'react'

/** A note box that starts as one line and grows a line at a time as you type, so you see it all. */
export default function NoteBox({ className, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  const ref = useRef<HTMLTextAreaElement>(null)
  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    el.style.height = 'auto'
    // scrollHeight leaves out the border.
    el.style.height = `${el.scrollHeight + el.offsetHeight - el.clientHeight}px`
  }, [props.value])
  return <textarea ref={ref} rows={1} className={`resize-none py-2.5 leading-snug ${className}`} {...props} />
}
