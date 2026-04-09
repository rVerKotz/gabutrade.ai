/// <reference types="react" />

declare module './hooks/useTradingEngine' {
  export function useTradingEngine(): any;
}

declare module './components/PriceChart' {
  const PriceChart: any;
  export default PriceChart;
}

declare module './components/OrderBook' {
  const OrderBook: any;
  export default OrderBook;
}

declare module './components/PortfolioPanel' {
  const PortfolioPanel: any;
  export default PortfolioPanel;
}

declare module './components/SignalBar' {
  const SignalBar: any;
  export default SignalBar;
}

declare module './components/AIPanel' {
  const AIPanel: any;
  export default AIPanel;
}

declare module './components/Header' {
  const Header: any;
  export default Header;
}
