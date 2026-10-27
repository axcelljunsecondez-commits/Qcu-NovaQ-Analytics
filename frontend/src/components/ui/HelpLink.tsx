import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { headingText } from '../../lib/headingText'
import type { HelpTopic } from '../../lib/helpGuides'

/** A contextual "?" that opens the Help center at one guide, and optionally one section of it. */
export function HelpLink({ topic, section }: { topic: HelpTopic; section?: string }) {
  const { t } = useTranslation()
  const title = headingText(t, `help.guide.${topic}.${section ? `${section}.title` : 'title'}`)
  return (
    <Link className="help-link" to={`/help/${topic}${section ? `#${section}` : ''}`}
      aria-label={t('help.open_guide', { title })} title={t('help.open_guide', { title })}>?</Link>
  )
}
