import { Outlet, useLocation } from 'react-router-dom'
import Navbar from './Navbar'

export default function Layout() {
  const location = useLocation()
  
  return (
    <div className="min-h-screen flex flex-col relative w-full" style={{ background: '#000', color: '#fff' }}>
      <Navbar />
      <div className="flex-1 flex flex-col relative w-full">
        {/* The key={location.key} ensures that navigating to the same route (e.g. clicking the logo)
            will force the component to unmount and remount, cleanly resetting all local useState variables! */}
        <Outlet key={location.key} />
      </div>
    </div>
  )
}
