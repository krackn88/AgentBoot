import { useState, useEffect } from 'react'

const KEY = 'apea-hub-v2'
const DEFAULTS = {
  completed: {}, bookmarks: [], quizHistory: [], answers: {},
  cardBox: {}, studyDates: [], plan: null, planDone: {}, deck: 'highyield',
  examDate: '', waitlist: [], lastChapter: null, fontSize: 17,
}
export function loadStore() {
  try { return { ...DEFAULTS, ...JSON.parse(localStorage.getItem(KEY) || '{}') } }
  catch { return { ...DEFAULTS } }
}
export function useStore() {
  const [store, setStore] = useState(loadStore)
  useEffect(() => { localStorage.setItem(KEY, JSON.stringify(store)) }, [store])
  const update = (fn) => setStore(s => (typeof fn === 'function' ? fn(s) : { ...s, ...fn }))
  return [store, update]
}
export function todayKey(d = new Date()) { return d.toISOString().slice(0, 10) }
export function streakOf(dates) {
  const set = new Set(dates); let streak = 0; const d = new Date()
  if (!set.has(todayKey(d))) d.setDate(d.getDate() - 1)
  while (set.has(todayKey(d))) { streak++; d.setDate(d.getDate() - 1) }
  return streak
}
export function shuffle(arr, seed) {
  const a = [...arr]; let s = seed ?? Math.floor(Math.random() * 1e9)
  for (let i = a.length - 1; i > 0; i--) { s = (s * 1103515245 + 12345) % 2147483648; const j = s % (i + 1);[a[i], a[j]] = [a[j], a[i]] }
  return a
}
