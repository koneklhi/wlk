import { SttMain } from '@/components/SttMain';
import { createFileRoute } from '@tanstack/react-router';

export const Route = createFileRoute('/')({
  component: () => (
    <div className="w-screen h-screen overflow-hidden">
      <SttMain />
    </div>
  ),
});
