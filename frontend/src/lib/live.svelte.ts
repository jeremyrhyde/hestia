import { LiveClient, type SocketLike, type Status } from './live';

export const connection: { status: Status } = $state({ status: 'connecting' });

export const live = new LiveClient({
  makeSocket: (url) => new WebSocket(url) as unknown as SocketLike,
  baseURI: () => document.baseURI,
  onStatus: (status) => {
    connection.status = status;
  },
});
