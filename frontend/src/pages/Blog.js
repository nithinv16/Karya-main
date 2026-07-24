import React from "react";
import { Link, useParams, Navigate } from "react-router-dom";
import { Helmet } from "react-helmet-async";
import { POSTS, BY_SLUG } from "@/blog";
import { ArrowLeft, Clock, Calendar } from "@phosphor-icons/react";

const SITE = "https://karyaai.app";

export function BlogIndex() {
  return (
    <div className="min-h-screen bg-white text-[#09090B]">
      <Helmet>
        <title>Blog — Karya AI | Notes on AI, construction, and shipping software</title>
        <meta
          name="description"
          content="Deep-dives on how Karya AI builds construction ops software with the Emergent platform, Telegram bots, cost analytics, and multi-language site management."
        />
        <link rel="canonical" href={`${SITE}/blog`} />
        <meta property="og:type" content="website" />
        <meta property="og:title" content="Karya AI — Blog" />
        <meta property="og:url" content={`${SITE}/blog`} />
        <meta property="og:image" content={`${SITE}/og-cover.png`} />
      </Helmet>

      <header className="border-b border-[#E4E4E7]">
        <div className="max-w-5xl mx-auto px-6 py-6 flex items-center justify-between">
          <Link to="/" className="font-display font-black text-lg tracking-tight" data-testid="blog-home-link">
            Karya<span className="text-[#EA580C]">.</span>
          </Link>
          <nav className="flex items-center gap-5 text-sm">
            <Link to="/blog" className="font-semibold text-[#09090B]">Blog</Link>
            <Link to="/pricing" className="text-[#71717A] hover:text-[#09090B]">Pricing</Link>
            <a href="https://t.me/karya_ops_bot" target="_blank" rel="noopener noreferrer" className="text-[#71717A] hover:text-[#09090B]">Telegram bot</a>
            <Link to="/" className="bg-[#EA580C] text-white px-4 py-2 font-semibold hover:bg-[#C2410C] transition-colors">
              Sign in
            </Link>
          </nav>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-16">
        <p className="overline text-[#EA580C]">Karya field notes</p>
        <h1 className="font-display font-black text-4xl sm:text-5xl tracking-tight mt-2">
          How we build software for the way sites actually run.
        </h1>
        <p className="text-lg text-[#3f3f46] mt-4 max-w-2xl leading-relaxed">
          Karya is an AI operating system for construction. We ship weekly. These posts are what we learned along the way — from choosing Emergent as our build platform, to why the primary interface is Telegram, to how we compute budget-vs-actual across three ledgers in real time.
        </p>

        <section className="mt-14 space-y-10" data-testid="blog-post-list">
          {POSTS.map((p) => (
            <article key={p.slug} className="border-t-2 border-[#09090B] pt-8">
              <Link to={`/blog/${p.slug}`} data-testid={`blog-post-${p.slug}`} className="block group">
                <div className="flex items-center gap-4 text-xs text-[#71717A] mb-2">
                  <span className="flex items-center gap-1"><Calendar size={12} />{p.date}</span>
                  <span className="flex items-center gap-1"><Clock size={12} />{p.readingTimeMin} min read</span>
                  {p.tags.slice(0, 2).map((t) => (
                    <span key={t} className="uppercase tracking-wider text-[10px] text-[#EA580C] font-bold">{t}</span>
                  ))}
                </div>
                <h2 className="font-display font-bold text-2xl tracking-tight leading-snug group-hover:text-[#EA580C] transition-colors">
                  {p.title}
                </h2>
                <p className="text-[#3f3f46] mt-2 leading-relaxed">{p.description}</p>
                <p className="inline-block mt-3 text-sm font-semibold text-[#EA580C] group-hover:underline">
                  Read the post →
                </p>
              </Link>
            </article>
          ))}
        </section>
      </main>

      <footer className="border-t border-[#E4E4E7] mt-24 py-10 text-center text-xs text-[#71717A]">
        © {new Date().getFullYear()} Karya AI · Built on{" "}
        <a href="https://emergent.sh" className="underline" target="_blank" rel="noopener noreferrer">
          Emergent.sh
        </a>
      </footer>
    </div>
  );
}

export function BlogPost() {
  const { slug } = useParams();
  const post = BY_SLUG[slug];
  if (!post) return <Navigate to="/blog" replace />;
  const Body = post.body;
  const url = `${SITE}/blog/${post.slug}`;

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "BlogPosting",
    "headline": post.title,
    "description": post.description,
    "datePublished": post.date,
    "dateModified": post.date,
    "author": { "@type": "Organization", "name": "Karya AI", "url": SITE },
    "publisher": {
      "@type": "Organization",
      "name": "Karya AI",
      "logo": { "@type": "ImageObject", "url": `${SITE}/icons/icon-512.png` },
    },
    "mainEntityOfPage": url,
    "keywords": post.tags.join(", "),
    "image": `${SITE}/og-cover.png`,
    "inLanguage": "en-IN",
  };

  return (
    <div className="min-h-screen bg-white text-[#09090B]">
      <Helmet>
        <title>{`${post.title} — Karya AI Blog`}</title>
        <meta name="description" content={post.description} />
        <link rel="canonical" href={url} />
        <meta name="robots" content="index, follow, max-image-preview:large" />
        <meta property="og:type" content="article" />
        <meta property="og:title" content={post.title} />
        <meta property="og:description" content={post.description} />
        <meta property="og:url" content={url} />
        <meta property="og:image" content={`${SITE}/og-cover.png`} />
        <meta property="article:published_time" content={post.date} />
        <meta name="twitter:card" content="summary_large_image" />
        <meta name="twitter:title" content={post.title} />
        <meta name="twitter:description" content={post.description} />
        <meta name="twitter:image" content={`${SITE}/og-cover.png`} />
        <script type="application/ld+json">{JSON.stringify(jsonLd)}</script>
      </Helmet>

      <header className="border-b border-[#E4E4E7]">
        <div className="max-w-5xl mx-auto px-6 py-6 flex items-center justify-between">
          <Link to="/" className="font-display font-black text-lg tracking-tight" data-testid="blog-home-link">
            Karya<span className="text-[#EA580C]">.</span>
          </Link>
          <nav className="flex items-center gap-5 text-sm">
            <Link to="/blog" className="text-[#71717A] hover:text-[#09090B]">Blog</Link>
            <Link to="/pricing" className="text-[#71717A] hover:text-[#09090B]">Pricing</Link>
            <Link to="/" className="bg-[#EA580C] text-white px-4 py-2 font-semibold hover:bg-[#C2410C] transition-colors">
              Sign in
            </Link>
          </nav>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-16">
        <Link to="/blog" className="inline-flex items-center gap-1.5 text-sm text-[#71717A] hover:text-[#EA580C] mb-8" data-testid="blog-back">
          <ArrowLeft size={14} /> All posts
        </Link>
        <div className="flex items-center gap-4 text-xs text-[#71717A] mb-3">
          <span className="flex items-center gap-1"><Calendar size={12} />{post.date}</span>
          <span className="flex items-center gap-1"><Clock size={12} />{post.readingTimeMin} min read</span>
        </div>
        <h1 className="font-display font-black text-3xl sm:text-4xl tracking-tight leading-tight">{post.title}</h1>
        <p className="text-lg text-[#3f3f46] mt-4 leading-relaxed">{post.description}</p>

        <article className="prose-karya mt-10">
          <Body />
        </article>

        <div className="mt-16 pt-8 border-t border-[#E4E4E7]">
          <p className="text-xs uppercase tracking-wider text-[#71717A] mb-3">More from Karya</p>
          <ul className="grid sm:grid-cols-2 gap-4">
            {POSTS.filter((p) => p.slug !== post.slug).slice(0, 2).map((p) => (
              <li key={p.slug}>
                <Link to={`/blog/${p.slug}`} className="block border border-[#E4E4E7] p-4 hover:border-[#EA580C] hover:text-[#EA580C] transition-colors">
                  <p className="font-display font-bold text-sm">{p.title}</p>
                  <p className="text-xs text-[#71717A] mt-1 line-clamp-2">{p.description}</p>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      </main>

      <footer className="border-t border-[#E4E4E7] mt-24 py-10 text-center text-xs text-[#71717A]">
        © {new Date().getFullYear()} Karya AI · Built on{" "}
        <a href="https://emergent.sh" className="underline" target="_blank" rel="noopener noreferrer">
          Emergent.sh
        </a>
      </footer>
    </div>
  );
}
