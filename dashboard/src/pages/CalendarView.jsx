import { useState, useEffect } from 'react'
import FullCalendar from '@fullcalendar/react'
import dayGridPlugin from '@fullcalendar/daygrid'
import timeGridPlugin from '@fullcalendar/timegrid'
import interactionPlugin from '@fullcalendar/interaction'
import { Calendar, Clock, Zap } from 'lucide-react'
import { getCalendarEvents, getMiraSchedule } from '../api/client'

export default function CalendarView() {
  const [events, setEvents] = useState([])
  const [schedule, setSchedule] = useState([])

  useEffect(() => {
    Promise.all([getCalendarEvents(), getMiraSchedule()])
      .then(([evts, sched]) => { setEvents(evts); setSchedule(sched) })
      .catch(console.error)
  }, [])

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold">Calendar</h1>
          <p className="text-gray-500 text-sm mt-1">Your schedule + Mira's schedule layered together</p>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-mira-500" />
            <span className="text-sm text-gray-400">Mira Tasks</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-teal-500" />
            <span className="text-sm text-gray-400">Your Calendar</span>
          </div>
        </div>
      </div>

      {/* Legend */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 mb-6">
        <div className="flex items-center gap-6 text-sm text-gray-400">
          <div className="flex items-center gap-2">
            <Zap size={14} className="text-mira-400" />
            <span>Mira scheduled tasks, briefings, trading checks</span>
          </div>
          <div className="flex items-center gap-2">
            <Calendar size={14} className="text-teal-400" />
            <span>Your Google Calendar events</span>
          </div>
          <div className="flex items-center gap-2">
            <Clock size={14} className="text-yellow-400" />
            <span>Recurring: briefing 7am, trading checks every 15min</span>
          </div>
        </div>
      </div>

      {/* Mira's Daily Schedule */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 mb-6">
        <h3 className="text-sm font-semibold text-gray-400 mb-3">MIRA'S RECURRING SCHEDULE</h3>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 text-sm">
          {schedule.map((s, i) => (
            <div key={i} className="bg-gray-800/50 rounded-lg p-3">
              <div className="text-mira-400 font-mono text-xs">{s.time}</div>
              <div className="text-gray-300">{s.task}</div>
              <div className="text-xs text-gray-600 mt-1">{s.frequency}</div>
            </div>
          ))}
        </div>
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
          events={events}
          height="auto"
          nowIndicator={true}
          slotMinTime="06:00:00"
          slotMaxTime="23:00:00"
          allDaySlot={true}
          weekends={true}
          eventClick={(info) => {
            const props = info.event.extendedProps || {}
            console.log('Event:', info.event.title, props)
          }}
        />
      </div>
    </div>
  )
}
