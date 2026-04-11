import { JarvisProvider } from "./context/JarvisContext";
import { AppShell } from "./components/AppShell";

export default function App() {
  return (
    <JarvisProvider>
      <AppShell />
    </JarvisProvider>
  );
}
