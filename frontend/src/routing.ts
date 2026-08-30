import { useEffect, useState } from 'react';

export type Route =
  | { name: 'research' | 'research-new' | 'research-runs' | 'research-questions' | 'library' | 'library-sources' | 'library-documents' | 'memory' | 'knowledge-graph' | 'dialogue' | 'settings' | 'not-found' }
  | { name: 'research-run' | 'library-document' | 'knowledge-graph-run'; id: string };

function decodeRouteSegment(segment: string): string {
  try {
    return decodeURIComponent(segment);
  } catch {
    return segment;
  }
}

export function parseRoute(pathname: string): Route {
  const path = pathname.replace(/\/+$/, '') || '/research';
  const run = path.match(/^\/research\/runs\/([^/]+)$/);
  if (run) return { name: 'research-run', id: decodeRouteSegment(run[1]) };
  const document = path.match(/^\/library\/documents\/([^/]+)$/);
  if (document) return { name: 'library-document', id: decodeRouteSegment(document[1]) };
  const graph = path.match(/^\/knowledge-graph\/([^/]+)$/);
  if (graph) return { name: 'knowledge-graph-run', id: decodeRouteSegment(graph[1]) };
  const routes: Record<string, Exclude<Route['name'], 'research-run' | 'library-document' | 'knowledge-graph-run'>> = {
    '/research': 'research',
    '/research/new': 'research-new',
    '/research/runs': 'research-runs',
    '/research/questions': 'research-questions',
    '/library': 'library',
    '/library/sources': 'library-sources',
    '/library/documents': 'library-documents',
    '/memory': 'memory',
    '/knowledge-graph': 'knowledge-graph',
    '/dialogue': 'dialogue',
    '/settings': 'settings',
  };
  return routes[path] ? { name: routes[path] } : { name: 'not-found' };
}

export function navigate(path: string): void {
  window.history.pushState({}, '', path);
  window.dispatchEvent(new PopStateEvent('popstate'));
}

export function useRoute(): Route {
  const [route, setRoute] = useState<Route>(() => parseRoute(window.location.pathname));
  useEffect(() => {
    const update = () => setRoute(parseRoute(window.location.pathname));
    window.addEventListener('popstate', update);
    return () => window.removeEventListener('popstate', update);
  }, []);
  return route;
}

export function routeView(route: Route): 'inquiry' | 'history' | 'questions' | 'library' | 'memory' | 'knowledge-graph' | 'dialogue' | 'settings' {
  if (route.name === 'research-runs' || route.name === 'research-run') return 'history';
  if (route.name === 'research-questions') return 'questions';
  if (route.name.startsWith('library')) return 'library';
  if (route.name === 'memory') return 'memory';
  if (route.name === 'knowledge-graph' || route.name === 'knowledge-graph-run') return 'knowledge-graph';
  if (route.name === 'dialogue') return 'dialogue';
  if (route.name === 'settings') return 'settings';
  return 'inquiry';
}
