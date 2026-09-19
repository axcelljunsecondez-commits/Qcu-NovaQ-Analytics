import { describe, expect, it, vi } from 'vitest'
import { fireEvent, screen } from '@testing-library/react'
import { renderWithProviders } from '../../test/test-utils'
import type { QueueBreak } from '../../api/types'
import { BreakEditor } from './BreakEditor'

const anchored: QueueBreak = {
  queue_id: 'a',
  scheduled_start_time: '11:00:00',
  duration_minutes: 30,
  break_name: 'Lunch',
  original_start_time: '10:00:00',
}

function renderEditor() {
  const onChange = vi.fn()
  renderWithProviders(<BreakEditor queueIds={['a', 'b']} breaks={[anchored]} onChange={onChange} />)
  return onChange
}

describe('BreakEditor optimizer anchor', () => {
  it('clears original_start_time when the start time is edited', () => {
    const onChange = renderEditor()
    fireEvent.change(screen.getByLabelText('Break start 1'), { target: { value: '12:30' } })
    const [saved] = onChange.mock.calls[0][0] as QueueBreak[]
    expect(saved).toEqual({ queue_id: 'a', scheduled_start_time: '12:30', duration_minutes: 30, break_name: 'Lunch' })
    expect('original_start_time' in saved).toBe(false)
  })

  it('keeps original_start_time when other fields are edited', () => {
    const onChange = renderEditor()
    fireEvent.change(screen.getByLabelText('Break duration 1 (minutes)'), { target: { value: '45' } })
    fireEvent.change(screen.getByLabelText('Break queue 1'), { target: { value: 'b' } })
    expect((onChange.mock.calls[0][0] as QueueBreak[])[0].original_start_time).toBe('10:00:00')
    expect((onChange.mock.calls[1][0] as QueueBreak[])[0].original_start_time).toBe('10:00:00')
  })
})
