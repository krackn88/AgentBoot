// Entry point for the render smoke test: everything the harness needs, bundled
// together so there is exactly one copy of React in play. Exposes a ready-made
// render function so the harness never has to touch React itself.
import { renderToString } from 'react-dom/server'
import App, { StudyApp } from '../src/App.jsx'
import HighYield from '../src/components/HighYield.jsx'
import Planner, { buildPlan } from '../src/components/Planner.jsx'
import Tests from '../src/components/Tests.jsx'
import Flashcards from '../src/components/Flashcards.jsx'
import SearchPanel from '../src/components/SearchPanel.jsx'
import Workbook, { ChapterWorkbook } from '../src/components/Workbook.jsx'

const h = (type, props) => ({ $$typeof: Symbol.for('react.transitional.element'), type, key: null, props: props || {} })

function renderNode(node) {
  return renderToString(node)
}

function renderApp(guide) {
  return renderToString(h(guide ? StudyApp : App, guide ? { guide } : {}))
}

export default {
  renderApp,
  renderNode,
  h,
  App,
  StudyApp,
  HighYield,
  Planner,
  buildPlan,
  Tests,
  Flashcards,
  SearchPanel,
  Workbook,
  ChapterWorkbook,
}
