import React from 'react'

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { err: null }
  }

  static getDerivedStateFromError(err) {
    return { err }
  }

  render() {
    if (this.state.err) {
      return (
        <div className="boot-screen">
          <div className="card boot-card">
            <p className="eyebrow">APEA FNP Study Hub</p>
            <h2>Something went wrong</h2>
            <p className="muted">This screen hit an unexpected error. Your progress in localStorage is usually still safe.</p>
            <p className="small muted" style={{ wordBreak: 'break-word' }}>{String(this.state.err.message || this.state.err)}</p>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 16 }}>
              <button type="button" className="btn" onClick={() => location.reload()}>Reload</button>
              <button type="button" className="btn ghost" onClick={() => { location.hash = '#/dashboard'; this.setState({ err: null }) }}>Back to dashboard</button>
            </div>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
