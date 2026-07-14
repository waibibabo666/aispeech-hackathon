import React from 'react';
import { TaskProvider } from './hooks/useTasks';
import Layout from './components/Layout';
import InputPanel from './components/InputPanel';
import TaskTimeline from './components/TaskTimeline';

export default function App() {
  return (
    <TaskProvider>
      <Layout>
        <InputPanel />
        <TaskTimeline />
      </Layout>
    </TaskProvider>
  );
}
