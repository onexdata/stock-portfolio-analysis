Coco AI - Take Home Project
Time Estimate: 4 hours
Overview
Build a backend service that provides real-time stock portfolio analysis. The system supports multiple concurrent portfolio sessions, each with isolated state. Clients can connect, request analysis on stocks in their portfolio, and receive streaming updates. The system must intelligently handle overlapping requests and maintain data consistency when multiple operations access shared state concurrently.
Core Requirements
1. Real-Time Client Communication
Support persistent connections between clients and server for portfolio sessions
Accept analysis requests with this structure:

{

  "action": "analyze",

  "ticker": "AAPL"

}

Stream analysis results back to clients as they become available:

{

  "type": "analysis_result",

  "ticker": "AAPL",

  "metric": "portfolio_risk",

  "value": 0.23,

  "timestamp": "2024-01-26T10:30:00Z"

}

Handle client disconnections and session management
2. Portfolio State Management
Store portfolio state in Redis as a single cohesive object per portfolio session:

{

  "session_id": "user-123",

  "holdings": {"AAPL": 100, "GOOGL": 50, "MSFT": 75},

  "total_value": 125000.00,

  "current_analysis": {

    "ticker": "AAPL",

    "started_at": "2024-01-26T10:00:00Z"

  },

  "analysis_results": [

    {"ticker": "AAPL", "metric": "portfolio_risk", "value": 0.23, "timestamp": "2024-01-26T09:55:00Z"},

    {"ticker": "GOOGL", "metric": "concentration", "value": 0.15, "timestamp": "2024-01-26T09:58:00Z"}

  ],

  "last_activity": "2024-01-26T10:00:00Z"

}

Three types of operations modify this state concurrently:
Client requests update current_analysis with the new ticker and last_activity timestamp
Analysis results are appended to analysis_results as metrics complete
Market data updates modify total_value based on current prices for all holdings
Ensure state consistency when operations overlap - corrupted state or lost updates are unacceptable
Portfolio sessions should expire after 24 hours of inactivity
3. Analysis Processing
When a user requests analysis for a ticker, start computing portfolio-context metrics for that stock
Compute these metrics in parallel: ["portfolio_risk", "concentration", "correlation", "momentum", "allocation_score"]
Each metric takes 2-5 seconds to compute independently and requires the user's complete portfolio context:
portfolio_risk: How this holding contributes to overall portfolio risk given the user's other positions
concentration: What percentage of the portfolio this represents and if it's overweighted
correlation: How this stock's movements relate to the user's other holdings
momentum: Trend analysis weighted by the user's position size
allocation_score: Whether the user should increase/decrease this position given their total portfolio
Analysis results drive investment decisions - returning analysis computed with stale portfolio values is unacceptable and could lead to incorrect recommendations
Stream each metric result to the client as it completes
Users exploring their portfolio will switch between different stocks to understand different positions
Before starting or restarting analysis, read the current portfolio state to get all holdings and position sizes
As each metric completes, append the result to analysis_results and stream it to the client
4. Background Market Updates
Simulate a background process that periodically updates portfolio values (every 30 seconds)
Each update must: read the current state, fetch mock price data for all holdings, recalculate total_value, and write back
These updates run continuously and independently of client requests
The system must handle scenarios where analysis completions and market updates occur simultaneously
Technical Stack
Python 3.10+
FastAPI
Redis for state storage (required)
asyncio for concurrency
Mock any external APIs (don't actually call real stock services)
Deliverables
Working Python backend service
README explaining your architectural approach and key design decisions
Simple way to demonstrate the system working (test script, example commands, etc.)



Note: This is intentionally underspecified. Part of the exercise is determining what guarantees the system should provide and how to achieve them. Document your assumptions and trade-offs.

