import { useTranslation } from 'react-i18next'
import { headingText } from '../../lib/headingText'
import { LineStructurePicture } from '../illustrations/LineStructurePicture'
import { ExpandablePanel } from './ExpandablePanel'

export function QueueTypesComparison({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const { t } = useTranslation()
  return <ExpandablePanel id="home-queue-types" className="home-queue-comparison" title={headingText(t, 'queueing101.queue_types')}
    description={t('queueing101.queue_types_comparison_description')} open={open} onOpenChange={onOpenChange}>
    <div className="home-queue-grid">
      {(['separate', 'shared'] as const).map((variant) => <article key={variant} className="home-queue-slide" aria-labelledby={`home-${variant}-title`}>
        <h3 lang="en" id={`home-${variant}-title`}>{headingText(t, `home.structure_${variant}_title`)}</h3>
        <p>{t(`home.structure_${variant}_desc`)}</p>
        <LineStructurePicture variant={variant} />
        <p className="home-note">{t(`home.structure_${variant}_example`)}</p>
      </article>)}
    </div>
    <p className="home-note">{t('home.pictures_note')}</p>
  </ExpandablePanel>
}
