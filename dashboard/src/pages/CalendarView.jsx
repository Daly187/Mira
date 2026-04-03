import { useState, useEffect, useCallback } from 'react'
import FullCalendar from '@fullcalendar/react'
import dayGridPlugin from '@fullcalendar/daygrid'
import timeGridPlugin from '@fullcalendar/timegrid'
import interactionPlugin from '@fullcalendar/interaction'
import { Calendar, Clock, Zap, Plus, X, Info } from 'lucide-react'
import { getCalendarEvents, getMiraSchedule, getScheduleHistory, createCalendarEvent } from '../api/client'

const EVENT_TYPES = {
  mira: { label: 'Mira Tasks', color: 'bg-mira-500', icon: Zap, iconColor: 'text-mira-400' },
  user: { label: 'Your Calendar', color: 'bg-teal-500', icon: Calendar, iconColor: 'text-teal-400' },
  recurring: { label: 'Recurring', color: 'bg-yellow-500', icon: Clock, iconColor: 'text-yellow-400' },
}

export default function CalendarView() {
  const [events, setEvents] = useState([])
  const [schedule, setSchedule] = useState([])
  const [scheduledTasks, setScheduledTasks] = useState([])
  const [filters, setFilters] = useState({ mira: true, user: true, recurring: true })
  const [showAddModal, setShowAddModal] = useState(false)
  const [selectedEvent, setSelectedEvent] = useState(null)
  const [newEvent, setNewEvent] = useState({ title: '', date: '', time: '', type: 'user_event', description: '' })

  const loadData = useCallback(() => {
    Promise.all([getCalendarEvents(), getMiraSchedule(), getScheduleHistory()])
      .then(([evts, sched, tasks]) => {
        setEvents(evts || [])
        setSchedule(sched || [])
        setScheduledTasks(tasks || [])
      })
      .catch(console.error)
  }, [])

  useEffect(() => { loadData() }, [loadData])

  const toggleFilter = (key) => {
    setFilters((prev) => ({ ...prev, [key]: !prev[key] }))
  }

  // Classify events by type for filtering
  const classifyEvent = (evt) => {
    const type = evt.type || evt.extendedProps?.type || ''
    if (type === 'google_calendar') return 'user'
    if (type === 'recurring') return 'recurring'
    return 'mira'
  }

  const filteredEvents = events.filter((evt) => {
    const cat = classifyEvent(evt)
    return filters[cat]
  })

  // Add recurring schedule items as all-day markers on today
  const recurringEvents = filters.recurring
    ? schedule.map((s, i) => ({
        id: `recurring-${i}`,
        title: `${s.time} - ${s.task}`,
        start: new Date().toISOString().split('T')[0],
        allDay: true,
        className: 'recurring-event',
        display: 'list-item',
        backgroundColor: '#eab308',
        borderColor: '#eab308',
        type: 'recurring',
      }))
    : []

  const allEvents = [...filteredEvents, ...recurringEvents]

  const handleAddEvent = async () => {
    if (!newEvent.title || !newEvent.date) return
    const start = newEvent.time
      ? `${newEvent.date}T${newEvent.time}:00`
      : newEvent.date
    try {
      await createCalendarEvent({
        title: newEvent.title,
        start,
        type: newEvent.type,
        description: newEvent.description,
      })
      setShowAddModal(false)
      setNewEvent({ title: '', date: '', time: '', type: 'user_event', description: '' })
      loadData()
    } catch (e) {
      console.error('Failed to create event:', e)
    }
  }

  const handleEventClick = (info) => {
    const props = info.event.extendedProps || {}
    setSelectedEvent({
      title: info.event.title,
      start: info.event.start?.toLocaleString() || '',
      end: info.event.end?.toLocaleString() || '',
      type: props.type || 'unknown',
      module: props.module || '',
      priority: props.priority || '',
      allDay: info.event.allDay,
    })
  }

  const handleDateClick = (info) => {
    setNewEvent((prev) => ({ ...prev, date: info.dateStr.split('T')[0], time: info.dateStr.includes('T') ? info.dateStr.split('T')[1]?.substring(0, 5) : '' }))
    setShowAddModal(true)
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold">Calendar</h1>
          <p className="text-gray-500 text-sm mt-1">Your schedule + Mira's schedule layered together</p>
        </div>
        <button
          onClick={() => setShowAddModal(true)}
          className="flex items-center gap-2 px-4 py-2 bg-mira-500 hover:bg-mira-600 text-white rounded-lg text-sm transition"
        >
          <Plus size={16} />
          Add Event
        </button>
      </div>

      {/* Toggleable Legend */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 mb-6">
        <div className="flex items-center gap-6 text-sm">
          {Object.entries(EVENT_TYPES).map(([key, cfg]) => {
            const Icon = cfg.icon
            const active = filters[key]
            return (
              <button
                key={key}
                onClick={() => toggleFilter(key)}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-lg transition ${
                  active
                    ? 'bg-gray-800 text-gray-200'
                    : 'bg-gray-900 text-gray-600 line-through opacity-50'
                }`}
              >
                <div className={`w-3 h-3 rounded-full ${cfg.color} ${!active ? 'opacity-30' : ''}`} />
                <Icon size={14} className={active ? cfg.iconColor : 'text-gray-600'} />
                <span>{cfg.label}</span>
              </button>
            )
          })}
        </div>
      </div>

      {/* Mira's Recurring Schedule — populated from getScheduleHistory */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 mb-6">
        <h3 className="text-sm font-semibold text-gray-400 mb-3">MIRA'S RECURRING SCHEDULE</h3>
        {scheduledTasks.length > 0 ? (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 text-sm">
            {scheduledTasks.map((task, i) => (
              <div key={i} className="bg-gray-800/50 rounded-lg p-3">
                <div className="text-mira-400 font-mono text-xs">{task.schedule || task.time || ''}</div>
                <div className="text-gray-300">{task.description || task.name || task.task || ''}</div>
                <div className="text-xs text-gray-600 mt-1">
                  {task.module && <span className="text-mira-500/60">{task.module}</span>}
                  {task.last_run && (
                    <span className="ml-2 text-gray-500">Last: {new Date(task.last_run).toLocaleDateString()}</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : schedule.length > 0 ? (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 text-sm">
            {schedule.map((s, i) => (
              <div key={i} className="bg-gray-800/50 rounded-lg p-3">
                <div className="text-mira-400 font-mono text-xs">{s.time}</div>
                <div className="text-gray-300">{s.task}</div>
                <div className="text-xs text-gray-600 mt-1">{s.frequency}</div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-gray-600 text-sm">No scheduled tasks found.</p>
        )}
      </div>

      {/* Full Calendar */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
        <FullCalendar
          plugins={[dayGridPlugin, timeGridPlugin, interactionPlugin]}
          initialView="timeGridWeek"
          headerToolbar={{
            left: 'prev,next today',
            center: 'title',
            right: 'dayGridMonth,timeGridWeek,timeGridDay',
          }}
          events={allEvents}
          height="auto"
          nowIndicator={true}
          slotMinTime="06:00:00"
          slotMaxTime="23:00:00"
          allDaySlot={true}
          weekends={true}
          selectable={true}
          dateClick={handleDateClick}
          eventClick={handleEventClick}
        />
      </div>

      {/* Add Event Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setShowAddModal(false)}>
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 w-full max-w-md" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-200">Add Event</h2>
              <button onClick={() => setShowAddModal(false)} className="text-gray-500 hover:text-gray-300">
                <X size={20} />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-xs text-gray-500 uppercase tracking-wider mb-1">Title</label>
                <input
                  type="text"
                  value={newEvent.title}
                  onChange={(e) => setNewEvent({ ...newEvent, title: e.target.value })}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-gray-200 text-sm focus:outline-none focus:border-mira-500"
                  placeholder="Event title..."
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-gray-500 uppercase tracking-wider mb-1">Date</label>
                  <input
                    type="date"
                    value={newEvent.date}
                    onChange={(e) => setNewEvent({ ...newEvent, date: e.target.value })}
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-gray-200 text-sm focus:outline-none focus:border-mira-500"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 uppercase tracking-wider mb-1">Time</label>
                  <input
                    type="time"
                    value={newEvent.time}
                    onChange={(e) => setNewEvent({ ...newEvent, time: e.target.value })}
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-gray-200 text-sm focus:outline-none focus:border-mira-500"
                  />
                </div>
              </div>
              <div>
                <label className="block text-xs text-gray-500 uppercase tracking-wider mb-1">Type</label>
                <select
                  value={newEvent.type}
                  onChange={(e) => setNewEvent({ ...newEvent, type: e.target.value })}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-gray-200 text-sm focus:outline-none focus:border-mira-500"
                >
                  <option value="user_event">Personal Event</option>
                  <option value="pa">PA / Meeting</option>
                  <option value="trading">Trading</option>
                  <option value="social">Social / Content</option>
                  <option value="personal">Health / Personal</option>
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-500 uppercase tracking-wider mb-1">Description</label>
                <textarea
                  value={newEvent.description}
                  onChange={(e) => setNewEvent({ ...newEvent, description: e.target.value })}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-gray-200 text-sm focus:outline-none focus:border-mira-500 h-20 resize-none"
                  placeholder="Optional description..."
                />
              </div>
              <button
                onClick={handleAddEvent}
                disabled={!newEvent.title || !newEvent.date}
                className="w-full bg-mira-500 hover:bg-mira-600 disabled:bg-gray-700 disabled:text-gray-500 text-white rounded-lg py-2 text-sm font-medium transition"
              >
                Create Event
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Event Detail Modal */}
      {selectedEvent && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setSelectedEvent(null)}>
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 w-full max-w-md" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-200">Event Details</h2>
              <button onClick={() => setSelectedEvent(null)} className="text-gray-500 hover:text-gray-300">
                <X size={20} />
              </button>
            </div>
            <div className="space-y-3">
              <div>
                <p className="text-xs text-gray-500 uppercase tracking-wider">Title</p>
                <p className="text-gray-200">{selectedEvent.title}</p>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <p className="text-xs text-gray-500 uppercase tracking-wider">Start</p>
                  <p className="text-gray-300 text-sm">{selectedEvent.start || 'N/A'}</p>
                </div>
                {selectedEvent.end && (
                  <div>
                    <p className="text-xs text-gray-500 uppercase tracking-wider">End</p>
                    <p className="text-gray-300 text-sm">{selectedEvent.end}</p>
                  </div>
                )}
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <p className="text-xs text-gray-500 uppercase tracking-wider">Type</p>
                  <p className="text-sm">
                    <span className={`px-2 py-0.5 rounded-full text-xs ${
                      selectedEvent.type === 'google_calendar'
                        ? 'bg-teal-500/20 text-teal-400'
                        : selectedEvent.type === 'recurring'
                        ? 'bg-yellow-500/20 text-yellow-400'
                        : 'bg-mira-500/20 text-mira-400'
                    }`}>
                      {selectedEvent.type.replace('_', ' ')}
                    </span>
                  </p>
                </div>
                {selectedEvent.module && (
                  <div>
                    <p className="text-xs text-gray-500 uppercase tracking-wider">Module</p>
                    <p className="text-gray-300 text-sm">{selectedEvent.module}</p>
                  </div>
                )}
              </div>
              {selectedEvent.priority && (
                <div>
                  <p className="text-xs text-gray-500 uppercase tracking-wider">Priority</p>
                  <p className="text-gray-300 text-sm">P{selectedEvent.priority}</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
