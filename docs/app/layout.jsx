import { Layout } from 'nextra-theme-docs'
import { Head } from 'nextra/components'
import { getPageMap } from 'nextra/page-map'
import 'nextra-theme-docs/style.css'
import '../styles.css'
import { Analytics } from '@vercel/analytics/react'
import CustomNavbar from '../components/Navbar/Navbar'
import CustomFooter from '../components/Footer/Footer'
import PostHogProvider from '../components/Analytics/PostHogProvider'

export const metadata = {
  title: {
    default: "St. Joseph's Placements and Training Cell Docs",
    template: "%s – St. Joseph's Placements and Training Cell Docs",
  },
  description:
    "Documentation for St. Joseph's Placements and Training Cell's learning platform. Guides for course creation, AI features, API reference, and more.",
  keywords: [
    "St. Joseph's Placements and Training Cell",
    'learning management system',
    'course creation',
    "St. Joseph's Placements and Training Cell documentation",
    "St. Joseph's Placements and Training Cell docs",
  ],
  robots: {
    index: false,
    follow: false,
    googleBot: {
      index: false,
      follow: false,
    },
  },
  openGraph: {
    type: 'website',
    locale: 'en_US',
    siteName: "St. Joseph's Placements and Training Cell Docs",
    description:
      "Documentation for St. Joseph's Placements and Training Cell's learning platform. Guides for course creation, AI features, API reference, and more.",
    images: [
      {
        url: '/img/og.png',
        alt: "St. Joseph's Placements and Training Cell Docs",
        width: 1512,
        height: 687,
      },
    ],
  },
  icons: {
    icon: [
      { url: '/favicons/favicon-32x32.png', sizes: '32x32', type: 'image/png' },
      { url: '/favicons/favicon-16x16.png', sizes: '16x16', type: 'image/png' },
    ],
    apple: '/favicons/apple-touch-icon.png',
  },
  manifest: '/favicons/site.webmanifest',
}

export default async function RootLayout({ children }) {
  return (
    <html lang="en" dir="ltr" suppressHydrationWarning>
      <Head faviconGlyph="">
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=Wix+Madefor+Text:ital,wght@0,400..700;1,400..700&display=swap" rel="stylesheet" />
        <link href="https://fonts.googleapis.com/css2?family=Wix+Madefor+Display:wght@600;700;800;900&display=swap" rel="stylesheet" />
        <link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&display=swap" rel="stylesheet" />
        <link href="https://fonts.googleapis.com/css2?family=Zilla+Slab:wght@400;500;600;700&display=swap" rel="stylesheet" />
      </Head>
      <body>
        <PostHogProvider>
          <CustomNavbar />
          <Layout
            pageMap={await getPageMap()}
            docsRepositoryBase="https://github.com/Shreesh-Sree/learnhouse-stjosephs/tree/main/docs"
            sidebar={{ defaultMenuCollapseLevel: 2 }}
            editLink="Edit this page on GitHub"
            footer={<></>}
            navbar={<></>}
            nextThemes={{ forcedTheme: 'light', defaultTheme: 'light' }}
          >
            {children}
          </Layout>
          <CustomFooter />
        </PostHogProvider>
        <Analytics />
      </body>
    </html>
  )
}
