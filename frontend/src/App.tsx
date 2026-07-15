import React from 'react';
import { TaskProvider } from './hooks/useTasks';
import Layout from './components/Layout';
import InputPanel from './components/InputPanel';
import TaskTimeline from './components/TaskTimeline';

export default function App() {
  return (
    <TaskProvider>
      <Layout>
        <div className="h-full flex flex-col gap-3">
          {/* Timeline — takes all available space, fills to window edge */}
          <div className="flex-1 min-h-0">
            <TaskTimeline />
          </div>
          {/* Input — pinned to bottom, fixed height */}
          <div className="flex-shrink-0">
            <InputPanel />
          </div>
        </div>
      </Layout>
    </TaskProvider>
  );
}
