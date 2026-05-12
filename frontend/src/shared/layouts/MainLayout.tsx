import { Layout } from 'antd';
import { Outlet } from 'react-router-dom';
import { Header } from './Header';
import { Sidebar } from './Sidebar';

export function MainLayout() {
  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header />
      <Layout>
        <Sidebar />
        <Layout>
          <Layout.Content
            style={{
              padding: 24,
              background: '#f5f5f5',
              minHeight: 'calc(100vh - 56px)',
            }}
          >
            <Outlet />
          </Layout.Content>
        </Layout>
      </Layout>
    </Layout>
  );
}
