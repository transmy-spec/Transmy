import { cleanup, fireEvent, render, screen } from '@testing-library/vue'
import axe from 'axe-core'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import App from './App.vue'

describe('App', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 401 }))
  })

  afterEach(() => {
    cleanup()
  })

  it('offers Keycloak login to anonymous users', async () => {
    render(App)

    expect(await screen.findByRole('heading', { level: 1, name: 'Bienvenue' })).toBeTruthy()
    expect(screen.getByRole('link', { name: /Se connecter avec Keycloak/ })).toBeTruthy()
    expect(screen.getByRole('main')).toBeTruthy()
    expect(document.querySelector('#main-content')).toBeTruthy()
  })

  it('has no automatically detectable WCAG 2.2 AA violation on login', async () => {
    render(App)
    await screen.findByRole('heading', { level: 1, name: 'Bienvenue' })

    const audit = await axe.run(document.body, {
      runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'] },
      rules: { 'color-contrast': { enabled: false } },
    })
    expect(audit.violations).toEqual([])
  })

  it('changes and remembers the interface language', async () => {
    render(App)
    await screen.findByRole('heading', { level: 1, name: 'Bienvenue' })

    await fireEvent.update(screen.getByRole('combobox', { name: /Langue de l.interface/ }), 'en')

    expect(await screen.findByRole('heading', { level: 1, name: 'Welcome' })).toBeTruthy()
    expect(screen.getByRole('link', { name: /Sign in with Keycloak/ })).toBeTruthy()
    expect(localStorage.getItem('transmissions.locale')).toBe('en')
    expect(document.documentElement.lang).toBe('en')
  })
})
