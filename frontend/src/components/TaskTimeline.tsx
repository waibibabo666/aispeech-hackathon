import React, { useState, useMemo, useRef, useCallback, useEffect } from 'react';
import FullCalendar from '@fullcalendar/react';
import timeGridPlugin from '@fullcalendar/timegrid';
import dayGridPlugin from '@fullcalendar/daygrid';
import listPlugin from '@fullcalendar/list';
import interactionPlugin from '@fullcalendar/interaction';
import type { EventClickArg, EventContentArg, DatesSetArg } from '@fullcalendar/core';
import { useTasks } from '../hooks/useTasks';
import type { Task, TaskKind } from '../types';
import TaskDetail from './TaskDetail';

const KIND_COLORS: Record<TaskKind, { bg: string; border: string; text: string }> = {
  event:     { bg: 'rgba(16, 185, 129, 0.10)', border: '#10b981', text: '#065f46' },
  deadline:  { bg: 'rgba(239, 68, 68, 0.10)',  border: '#ef4444', text: '#991b1b' },
  milestone: { bg: 'rgba(168, 85, 247, 0.10)', border: '#a855f7', text: '#6b21a8' },
};

const KIND_ICONS: Record<TaskKind, string> = {
  event:     '📅',
  deadline:  '🔴',
  milestone: '⭐',
};

const KIND_LABELS: Record<TaskKind, string> = {
  event:     '事件',
  deadline:  '截止',
  milestone: '纪念',
};

/** Find event tasks whose time ranges overlap. Returns a Set of conflicting task IDs. */
function findConflicts(tasks: Task[]): Set<string> {
  const events = tasks.filter(t => t.kind === 'event' && t.end_datetime);
  const conflicts = new Set<string>();
  for (let i = 0; i < events.length; i++) {
    const a = events[i];
    const aStart = new Date(a.datetime).getTime();
    const aEnd = new Date(a.end_datetime!).getTime();
    for (let j = i + 1; j < events.length; j++) {
      const b = events[j];
      const bStart = new Date(b.datetime).getTime();
      const bEnd = new Date(b.end_datetime!).getTime();
      if (aStart < bEnd && bStart < aEnd) {
        conflicts.add(a.id);
        conflicts.add(b.id);
      }
    }
  }
  return conflicts;
}

function taskToEvent(task: Task, conflictIds: Set<string>) {
  const colors = KIND_COLORS[task.kind] || KIND_COLORS.event;
  const isPoint = task.kind === 'deadline' || task.kind === 'milestone';
  const conflict = conflictIds.has(task.id);

  return {
    id: task.id,
    title: task.title,
    start: task.datetime,
    end: isPoint ? undefined : (task.end_datetime || undefined),
    allDay: isPoint,
    backgroundColor: conflict ? 'rgba(239,68,68,0.12)' : colors.bg,
    borderColor: conflict ? '#ef4444' : colors.border,
    textColor: conflict ? '#991b1b' : colors.text,
    classNames: [`fc-task-${task.kind}`, ...(conflict ? ['fc-task-conflict'] : [])],
    extendedProps: { task },
  };
}

function renderEventContent(info: EventContentArg) {
  const task = info.event.extendedProps.task as Task;
  const kind = (task.kind || 'event') as TaskKind;
  const icon = KIND_ICONS[kind];
  const isPointTask = kind === 'deadline' || kind === 'milestone';

  return (
    <div className={`fc-custom-event ${isPointTask ? 'fc-point-task' : ''}`}>
      <span className="fc-event-icon">{icon}</span>
      <span className="fc-event-title">
        {task.location ? (
          <>{info.event.title}<span className="fc-event-loc">{task.location}</span></>
        ) : (
          info.event.title
        )}
      </span>
    </div>
  );
}

function formatTitle(dates: { start: Date; end: Date }, viewType: string): string {
  const fmt = (d: Date) =>
    d.toLocaleDateString('zh-CN', { month: 'long', day: 'numeric' });

  switch (viewType) {
    case 'timeGridDay':
      return dates.start.toLocaleDateString('zh-CN', {
        year: 'numeric', month: 'long', day: 'numeric', weekday: 'short',
      });
    case 'timeGridWeek': {
      const end = new Date(dates.end);
      end.setDate(end.getDate() - 1); // FullCalendar end is exclusive
      return `${fmt(dates.start)} － ${fmt(end)}`;
    }
    case 'dayGridMonth':
      return dates.start.toLocaleDateString('zh-CN', { year: 'numeric', month: 'long' });
    case 'listWeek':
      return '任务列表';
    default:
      return '';
  }
}

export default function TaskTimeline() {
  const { tasks, deleteTask } = useTasks();
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [title, setTitle] = useState('');
  const [eventKey, setEventKey] = useState(0);  // bump on tasks change to force FullCalendar re-render
  const calendarRef = useRef<FullCalendar>(null);

  const events = useMemo(() => {
    const conflictIds = findConflicts(tasks);
    return tasks.map(t => taskToEvent(t, conflictIds));
  }, [tasks]);

  // Force FullCalendar to re-ingest events after updates
  useEffect(() => {
    setEventKey(k => k + 1);
  }, [tasks]);

  const handleEventClick = (info: EventClickArg) => {
    setSelectedTask(info.event.extendedProps.task as Task);
  };

  const handleDatesSet = useCallback((info: DatesSetArg) => {
    setTitle(formatTitle({ start: info.start, end: info.end }, info.view.type));
  }, []);

  return (
    <div className="h-full flex flex-col bg-white rounded-xl shadow-sm border border-gray-200">
      {/* Top bar: kind legend (left) */}
      <div className="flex-shrink-0 flex items-center justify-between px-4 py-2 border-b border-gray-100">
        <div className="flex items-center gap-1.5 text-[10px] text-gray-500">
          <span className="font-medium text-gray-600">图例</span>
          {(['event', 'deadline', 'milestone'] as TaskKind[]).map((k) => (
            <span key={k} className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-gray-50">
              {KIND_ICONS[k]} {KIND_LABELS[k]}
            </span>
          ))}
        </div>
        {title && (
          <span className="text-xs font-semibold text-gray-700">{title}</span>
        )}
        <div className="w-20" />{/* spacer for balance */}
      </div>

      {/* Calendar — let FullCalendar own the toolbar */}
      <div className="flex-1 min-h-0">
        <FullCalendar
          key={eventKey}
          ref={calendarRef}
          plugins={[timeGridPlugin, dayGridPlugin, listPlugin, interactionPlugin]}
          initialView="timeGridWeek"
          events={events}
          eventClick={handleEventClick}
          eventContent={renderEventContent}
          datesSet={handleDatesSet}
          headerToolbar={{
            left:   'prev,next today',
            center: 'title',
            right:  'timeGridDay,timeGridWeek,dayGridMonth,listWeek',
          }}
          buttonText={{
            today:    '今天',
            month:    '月',
            week:     '周',
            day:      '日',
            list:     '列表',
          }}
          height="100%"
          locale="zh-cn"
          firstDay={1}
          allDaySlot={true}
          nowIndicator={true}
          expandRows={true}
          slotEventOverlap={false}
          stickyHeaderDates={true}
          views={{
            timeGridDay: {
              titleFormat: { year: 'numeric', month: 'long', day: 'numeric', weekday: 'short' },
            },
            timeGridWeek: {
              titleFormat: { year: 'numeric', month: 'long' },
            },
            dayGridMonth: {
              titleFormat: { year: 'numeric', month: 'long' },
            },
            listWeek: {
              titleFormat: { year: 'numeric', month: 'long' },
            },
          }}
          noEventsContent={
            <div className="flex items-center justify-center h-full text-gray-400">
              <div className="text-center">
                <div className="text-3xl mb-2">📭</div>
                <p className="text-sm">暂无任务，在下方输入文本或上传文件开始</p>
              </div>
            </div>
          }
        />
      </div>

      {selectedTask && (
        <TaskDetail
          task={selectedTask}
          onClose={() => setSelectedTask(null)}
          onDelete={(id) => {
            deleteTask(id);
            setSelectedTask(null);
          }}
        />
      )}
    </div>
  );
}
