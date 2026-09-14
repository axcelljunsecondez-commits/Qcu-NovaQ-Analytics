import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../test/test-utils'
import { DatasetsPage } from './DatasetsPage'

const listDatasetsMock = vi.fn()
const uploadDatasetMock = vi.fn()
const deleteDatasetMock = vi.fn()

vi.mock('../api/datasets', () => ({
  listDatasets: (...args: unknown[]) => listDatasetsMock(...args),
  uploadDataset: (...args: unknown[]) => uploadDatasetMock(...args),
  deleteDataset: (...args: unknown[]) => deleteDatasetMock(...args),
}))

vi.mock('../api/auth', () => ({
  me: vi.fn(async () => ({
    user: { id: 1, email: 'a@b.c', role: 'admin', active: true, created_at: '2026-01-01T00:00:00Z' },
  })),
  login: vi.fn(async () => ({})),
  logout: vi.fn(async () => ({})),
}))

const dataset = {
  id: 1,
  name: 'sample',
  source_filename: 'sample.csv',
  source_format: 'csv',
  row_count: 4,
  validation: { ok: true, message: 'Input data is valid.' },
  created_at: '2026-08-01T10:00:00Z',
  normalized: null,
}

const invalidDataset = {
  ...dataset,
  id: 2,
  name: 'bad',
  validation: { ok: false, message: 'Missing column: mu' },
}

beforeEach(() => {
  listDatasetsMock.mockReset()
  uploadDatasetMock.mockReset()
  deleteDatasetMock.mockReset()
  listDatasetsMock.mockResolvedValue({ datasets: [dataset] })
})

describe('DatasetsPage', () => {
  it('renders the upload zone and dataset list', async () => {
    renderWithProviders(<DatasetsPage />, { route: '/datasets' })
    expect(await screen.findByText('sample')).toBeInTheDocument()
    expect(screen.getByText('sample.csv')).toBeInTheDocument()
    expect(screen.getByText('4')).toBeInTheDocument()
  })

  it('uploads a file and shows the success banner', async () => {
    uploadDatasetMock.mockResolvedValue({ dataset: dataset })
    const user = userEvent.setup()
    renderWithProviders(<DatasetsPage />, { route: '/datasets' })
    const file = new File(['time,lambda,mu,c\n'], 'segments.csv', { type: 'text/csv' })
    const input = screen.getByLabelText('File') as HTMLInputElement
    await user.upload(input, file)
    await user.click(screen.getByRole('button', { name: 'Upload dataset' }))
    await waitFor(() => {
      expect(uploadDatasetMock).toHaveBeenCalled()
    })
    expect(await screen.findByText('Input data is valid.')).toBeInTheDocument()
  })

  it('shows the validation failure message from the server', async () => {
    uploadDatasetMock.mockResolvedValue({ dataset: invalidDataset })
    const user = userEvent.setup()
    renderWithProviders(<DatasetsPage />, { route: '/datasets' })
    const file = new File(['nope'], 'bad.csv', { type: 'text/csv' })
    await user.upload(screen.getByLabelText('File'), file)
    await user.click(screen.getByRole('button', { name: 'Upload dataset' }))
    expect(
      await screen.findByText((content) => content.includes('Missing column: mu')),
    ).toBeInTheDocument()
  })

  it('shows a translated upload error when the API rejects', async () => {
    uploadDatasetMock.mockRejectedValue({ response: { status: 422 } })
    const user = userEvent.setup()
    renderWithProviders(<DatasetsPage />, { route: '/datasets' })
    const file = new File(['nope'], 'bad.csv', { type: 'text/csv' })
    await user.upload(screen.getByLabelText('File'), file)
    await user.click(screen.getByRole('button', { name: 'Upload dataset' }))
    expect(
      await screen.findByText((content) =>
        content.includes('Upload failed. Please check the file and try again.'),
      ),
    ).toBeInTheDocument()
  })

  it('deletes a dataset and refetches the list', async () => {
    deleteDatasetMock.mockResolvedValue({})
    const user = userEvent.setup()
    renderWithProviders(<DatasetsPage />, { route: '/datasets' })
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    await user.click(await screen.findByRole('button', { name: 'Delete' }))
    await waitFor(() => {
      expect(deleteDatasetMock).toHaveBeenCalledWith(1)
    })
  })

  it('shows empty state when there are no datasets', async () => {
    listDatasetsMock.mockResolvedValue({ datasets: [] })
    renderWithProviders(<DatasetsPage />, { route: '/datasets' })
    expect(await screen.findByText('No datasets yet.')).toBeInTheDocument()
  })
})
