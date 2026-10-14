import { beforeEach, describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../test/test-utils'
import { PreferencesSettings } from './PreferencesSettings'

const getPreferencesMock = vi.fn()
const savePreferencesMock = vi.fn()
vi.mock('../../api/preferences', () => ({
  getPreferences: (...args: unknown[]) => getPreferencesMock(...args),
  savePreferences: (...args: unknown[]) => savePreferencesMock(...args),
}))
vi.mock('../../api/auth', () => ({
  me: vi.fn(async () => ({ user: null })),
  login: vi.fn(),
  logout: vi.fn(),
}))

const empty = { operation_type: null, preferred_terminology: {} }

beforeEach(() => {
  getPreferencesMock.mockReset()
  savePreferencesMock.mockReset()
  savePreferencesMock.mockImplementation(async (body) => body)
})

describe('Settings → Preferences (spec §7.10, B1)', () => {
  it('starts empty for a user who never saved preferences and says labels do not change yet', async () => {
    getPreferencesMock.mockResolvedValue(empty)
    renderWithProviders(<PreferencesSettings />)
    expect(await screen.findByLabelText('Operation type')).toHaveValue('')
    expect(screen.getByLabelText('What do you call service points?')).toHaveValue('')
    expect(screen.getByLabelText('What do you call people receiving service?')).toHaveValue('')
    expect(screen.getByText('Saved for future use; NovaQ labels do not change yet.')).toBeInTheDocument()
  })

  it('saving with nothing chosen sends nothing to fill in', async () => {
    getPreferencesMock.mockResolvedValue(empty)
    const user = userEvent.setup()
    renderWithProviders(<PreferencesSettings />)
    await user.click(await screen.findByRole('button', { name: 'Save preferences' }))
    expect(savePreferencesMock).toHaveBeenCalledWith(empty, expect.anything())
    expect(await screen.findByRole('status')).toHaveTextContent('Preferences saved.')
  })

  it('saves exactly the chosen values, with typed names for Other', async () => {
    getPreferencesMock.mockResolvedValue(empty)
    const user = userEvent.setup()
    renderWithProviders(<PreferencesSettings />)
    await user.selectOptions(await screen.findByLabelText('Operation type'), 'retail')
    await user.selectOptions(screen.getByLabelText('What do you call service points?'), 'other')
    await user.type(screen.getByLabelText('Name for more than one'), ' Pay points ')
    await user.type(screen.getByLabelText('Name for one'), 'Pay point')
    await user.selectOptions(screen.getByLabelText('What do you call people receiving service?'), 'customers')
    await user.click(screen.getByRole('button', { name: 'Save preferences' }))
    expect(savePreferencesMock).toHaveBeenCalledWith({
      operation_type: 'retail',
      preferred_terminology: {
        service_point: 'other',
        service_point_label: 'Pay points',
        service_point_label_singular: 'Pay point',
        customer: 'customers',
      },
    }, expect.anything())
  })

  it('does not save Other without its names', async () => {
    getPreferencesMock.mockResolvedValue(empty)
    const user = userEvent.setup()
    renderWithProviders(<PreferencesSettings />)
    await user.selectOptions(await screen.findByLabelText('Operation type'), 'other')
    await user.click(screen.getByRole('button', { name: 'Save preferences' }))
    expect(savePreferencesMock).not.toHaveBeenCalled()
  })

  it('shows values saved earlier, including onboarding answers', async () => {
    getPreferencesMock.mockResolvedValue({
      operation_type: 'other',
      preferred_terminology: { operation_label: 'Laundry shop', service_point: 'tellers', customer: 'clients' },
    })
    renderWithProviders(<PreferencesSettings />)
    expect(await screen.findByLabelText('Operation type')).toHaveValue('other')
    expect(screen.getByLabelText('Name your operation')).toHaveValue('Laundry shop')
    expect(screen.getByLabelText('What do you call service points?')).toHaveValue('tellers')
    expect(screen.getByLabelText('What do you call people receiving service?')).toHaveValue('clients')
  })

  it('reports a failed save', async () => {
    getPreferencesMock.mockResolvedValue(empty)
    savePreferencesMock.mockRejectedValue(new Error('network'))
    const user = userEvent.setup()
    renderWithProviders(<PreferencesSettings />)
    await user.click(await screen.findByRole('button', { name: 'Save preferences' }))
    expect(await screen.findByRole('alert')).toBeInTheDocument()
  })
})
