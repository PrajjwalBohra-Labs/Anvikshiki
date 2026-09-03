import { useEffect, useState } from 'react';

export type Route =
<<<<<<< HEAD
  | { name: 'research' | 'research-new' | 'research-runs' | 'research-questions' | 'research-jobs' | 'library' | 'library-sources' | 'library-documents' | 'memory' | 'dialogue' | 'settings' | 'knowledge-graph' | 'notebook' | 'not-found' }
  | { name: 'research-run' | 'library-document' | 'knowledge-graph-run'; id: string };
=======
  | { name: 'research' | 'research-new' | 'research-runs' | 'research-questions' | 'library' | 'library-sources' | 'library-documents' | 'memory' | 'knowledge-graph' | 'notebook' | 'dialogue' | 'settings' | 'not-found' }
  | { name: 'research-run' | 'library-document' | 'knowledge-graph-run' | 'notebook-entry'; id: string };

function decodeRouteSegment(segment: string): string {
  try {
    return decodeURIComponent(segment);
  } catch {
    return segment;
  }
}
>>>>>>> eb3e53806e8a5a05b49d42f5fe8100352a92335f

export function parseRoute(pathname: string): Route {
  const path = pathname.replace(/\/+$/, '') || '/research';
  const run = path.match(/^\/research\/runs\/([^/]+)$/);
  if (run) return { name: 'research-run', id: decodeRouteSegment(run[1]) };
  const document = path.match(/^\/library\/documents\/([^/]+)$/);
<<<<<<< HEAD
  if (document) return { name: 'library-document', id: decodeURIComponent(document[1]) };
  const graph = path.match(/^\/knowledge-graph\/([^/]+)$/);
  if (graph) return { name: 'knowledge-graph-run', id: decodeURIComponent(graph[1]) };
  const routes: Record<string, Exclude<Route['name'], 'research-run' | 'library-document' | 'knowledge-graph-run'>> = {
=======
  if (document) return { name: 'library-document', id: decodeRouteSegment(document[1]) };
  const graph = path.match(/^\/knowledge-graph\/([^/]+)$/);
  if (graph) return { name: 'knowledge-graph-run', id: decodeRouteSegment(graph[1]) };
  const notebook = path.match(/^\/notebook\/([^/]+)$/);
  if (notebook) return { name: 'notebook-entry', id: decodeRouteSegment(notebook[1]) };
  const routes: Record<string, Exclude<Route['name'], 'research-run' | 'library-document' | 'knowledge-graph-run' | 'notebook-entry'>> = {
>>>>>>> eb3e53806e8a5a05b49d42f5fe8100352a92335f
    '/research': 'research',
    '/research/new': 'research-new',
    '/research/runs': 'research-runs',
    '/research/questions': 'research-questions',
    '/research/jobs': 'research-jobs',
    '/library': 'library',
    '/library/sources': 'library-sources',
    '/library/documents': 'library-documents',
    '/memory': 'memory',
    '/knowledge-graph': 'knowledge-graph',
    '/notebook': 'notebook',
    '/dialogue': 'dialogue',
    '/settings': 'settings',
    '/knowledge-graph': 'knowledge-graph',
    '/notebook': 'notebook',
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

export function routeView(route: Route): 'inquiry' | 'history' | 'questions' | 'library' | 'memory' | 'knowledge-graph' | 'notebook' | 'dialogue' | 'settings' {
  if (route.name === 'research-runs' || route.name === 'research-run') return 'history';
  if (route.name === 'research-questions') return 'questions';
  if (route.name.startsWith('library')) return 'library';
  if (route.name === 'memory') return 'memory';
  if (route.name === 'knowledge-graph' || route.name === 'knowledge-graph-run') return 'knowledge-graph';
  if (route.name === 'notebook' || route.name === 'notebook-entry') return 'notebook';
  if (route.name === 'dialogue') return 'dialogue';
  if (route.name === 'settings') return 'settings';
  if (route.name === 'knowledge-graph' || route.name === 'knowledge-graph-run') return 'memory';
  if (route.name === 'notebook') return 'inquiry';
  return 'inquiry';
}
