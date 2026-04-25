# Hera Home Automation Makefile
# Complete development environment for frontend and backend

# Variables
FRONTEND_DIR = frontend
BACKEND_DIR = .
FRONTEND_NODE_MODULES = $(FRONTEND_DIR)/node_modules
BACKEND_NODE_MODULES = node_modules
FRONTEND_PACKAGE_JSON = $(FRONTEND_DIR)/package.json
BACKEND_PACKAGE_JSON = package.json
DIST_DIR = $(FRONTEND_DIR)/dist

# Default target
.PHONY: help
help:
	@echo "Hera Home Automation Build System"
	@echo "================================="
	@echo ""
	@echo "Development Commands:"
	@echo "  install-all    - Install all dependencies (frontend + backend)"
	@echo "  install-fe     - Install frontend dependencies only"
	@echo "  install-be     - Install backend dependencies only"
	@echo "  dev-full       - Start both backend and frontend servers"
	@echo "  dev-backend    - Start backend server only (port 3001)"
	@echo "  dev-frontend   - Start frontend server only (port 3000)"
	@echo "  dev            - Alias for dev-frontend (requires backend running)"
	@echo ""
	@echo "Build Commands:"
	@echo "  build          - Build frontend for production"
	@echo "  preview        - Preview production build"
	@echo "  lint           - Run ESLint with auto-fix"
	@echo ""
	@echo "Maintenance Commands:"
	@echo "  clean          - Clean all build artifacts and dependencies"
	@echo "  clean-dist     - Clean only build output"
	@echo "  clean-deps     - Clean only node_modules"
	@echo "  info           - Show project information"
	@echo "  check-deps     - Check if dependencies are installed"
	@echo ""
	@echo "Quick Start:"
	@echo "  make install-all && make dev-full"
	@echo ""
	@echo "Frontend Only Development:"
	@echo "  make install-fe && make dev"

# Install dependencies
.PHONY: install-all
install-all: install-be install-fe
	@echo "All dependencies installed successfully!"

.PHONY: install-fe
install-fe:
	@echo "Installing frontend dependencies..."
	cd $(FRONTEND_DIR) && npm install

.PHONY: install-be
install-be:
	@echo "Installing backend dependencies..."
	npm install

.PHONY: install
install: install-fe
	@echo "Frontend dependencies installed!"

# Backend server
.PHONY: dev-backend
dev-backend:
	@echo "Starting backend server on http://localhost:3001"
	@if [ ! -d "$(BACKEND_NODE_MODULES)" ]; then \
		echo "Backend dependencies not found. Installing..."; \
		npm install; \
	fi
	node src/server.js

# Full development environment
.PHONY: dev-full
dev-full:
	@echo "Starting full development environment..."
	@echo "Backend will start on http://localhost:3001"
	@echo "Frontend will start on http://localhost:3000"
	@if [ ! -d "$(BACKEND_NODE_MODULES)" ]; then \
		echo "Backend dependencies not found. Installing..."; \
		npm install; \
	fi
	@if [ ! -d "$(FRONTEND_NODE_MODULES)" ]; then \
		echo "Frontend dependencies not found. Installing..."; \
		cd $(FRONTEND_DIR) && npm install; \
	fi
	@echo "Starting backend server..."
	node src/server.js &
	@sleep 3
	@echo "Starting frontend development server..."
	cd $(FRONTEND_DIR) && npm run dev

# Frontend development server
.PHONY: dev-frontend
dev-frontend:
	@echo "Starting frontend development server on http://localhost:3000"
	@echo "⚠️  Make sure backend server is running on http://localhost:3001"
	@echo "   Run 'make dev-backend' in another terminal if needed"
	@if [ ! -d "$(FRONTEND_NODE_MODULES)" ]; then \
		echo "Frontend dependencies not found. Installing..."; \
		cd $(FRONTEND_DIR) && npm install; \
	fi
	cd $(FRONTEND_DIR) && npm run dev

$(FRONTEND_NODE_MODULES): $(FRONTEND_PACKAGE_JSON)
	@echo "Installing frontend dependencies..."
	cd $(FRONTEND_DIR) && npm install
	@touch $(FRONTEND_NODE_MODULES)

$(BACKEND_NODE_MODULES): $(BACKEND_PACKAGE_JSON)
	@echo "Installing backend dependencies..."
	npm install
	@touch $(BACKEND_NODE_MODULES)

# Development server (alias for dev-frontend)
.PHONY: dev
dev: dev-frontend

# Production build
.PHONY: build
build:
	@echo "Building frontend for production..."
	@if [ ! -d "$(FRONTEND_NODE_MODULES)" ]; then \
		echo "Frontend dependencies not found. Installing..."; \
		cd $(FRONTEND_DIR) && npm install; \
	fi
	cd $(FRONTEND_DIR) && npm run build
	@echo "Build complete! Output in $(DIST_DIR)"

# Preview production build
.PHONY: preview
preview: $(DIST_DIR)
	@echo "Starting preview server for production build..."
	cd $(FRONTEND_DIR) && npm run preview

# Lint code
.PHONY: lint
lint:
	@echo "Running ESLint with auto-fix..."
	@if [ ! -d "$(FRONTEND_NODE_MODULES)" ]; then \
		echo "Frontend dependencies not found. Installing..."; \
		cd $(FRONTEND_DIR) && npm install; \
	fi
	cd $(FRONTEND_DIR) && npm run lint

# Clean targets
.PHONY: clean
clean: clean-dist clean-deps
	@echo "Cleaned all build artifacts and dependencies"

.PHONY: clean-dist
clean-dist:
	@echo "Cleaning build output..."
	rm -rf $(DIST_DIR)

.PHONY: clean-deps
clean-deps:
	@echo "Cleaning all node_modules..."
	rm -rf $(FRONTEND_NODE_MODULES)
	rm -rf $(BACKEND_NODE_MODULES)
	rm -f $(FRONTEND_DIR)/package-lock.json
	rm -f package-lock.json

# Utility targets
.PHONY: check-deps
check-deps:
	@echo "Checking dependencies..."
	@if [ -d "$(FRONTEND_NODE_MODULES)" ]; then \
		echo "✓ Frontend dependencies are installed"; \
	else \
		echo "✗ Frontend dependencies not found. Run 'make install-fe'"; \
	fi
	@if [ -d "$(BACKEND_NODE_MODULES)" ]; then \
		echo "✓ Backend dependencies are installed"; \
	else \
		echo "✗ Backend dependencies not found. Run 'make install-be'"; \
	fi

.PHONY: info
info:
	@echo "Hera Home Automation Project Information"
	@echo "========================================"
	@echo "Frontend Directory: $(FRONTEND_DIR)"
	@echo "Backend Directory:  $(BACKEND_DIR)"
	@echo "Build Output:       $(DIST_DIR)"
	@echo ""
	@echo "Development Servers:"
	@echo "- Frontend:         http://localhost:3000"
	@echo "- Backend:          http://localhost:3001"
	@echo ""
	@echo "Technology Stack:"
	@echo "Frontend:"
	@echo "- Vue.js 3"
	@echo "- Vite (build tool)"
	@echo "- Tailwind CSS"
	@echo "- Vue Router"
	@echo "- Pinia (state management)"
	@echo "- Socket.io client"
	@echo ""
	@echo "Backend:"
	@echo "- Node.js"
	@echo "- Express.js"
	@echo "- Socket.io server"
	@echo "- Home automation adapters"
	@echo ""
	@echo "Dependencies Status:"
	@if [ -d "$(FRONTEND_NODE_MODULES)" ]; then \
		echo "Frontend: ✓ Installed"; \
	else \
		echo "Frontend: ✗ Not installed"; \
	fi
	@if [ -d "$(BACKEND_NODE_MODULES)" ]; then \
		echo "Backend:  ✓ Installed"; \
	else \
		echo "Backend:  ✗ Not installed"; \
	fi
	@if [ -d "$(DIST_DIR)" ]; then \
		echo "Build:    ✓ Built"; \
	else \
		echo "Build:    ✗ Not built"; \
	fi

# Force rebuild
.PHONY: rebuild
rebuild: clean-dist build
	@echo "Frontend rebuilt successfully"

# Quick development setup
.PHONY: setup
setup: install-all
	@echo "Full project setup complete!"
	@echo "Run 'make dev-full' to start both servers"
	@echo "Or run 'make dev-backend' and 'make dev-frontend' in separate terminals"

# Check for required tools
.PHONY: check-tools
check-tools:
	@echo "Checking required tools..."
	@command -v node >/dev/null 2>&1 || { echo "✗ Node.js is required but not installed"; exit 1; }
	@command -v npm >/dev/null 2>&1 || { echo "✗ npm is required but not installed"; exit 1; }
	@echo "✓ Node.js and npm are available"
	@node --version
	@npm --version

# Stop all development servers
.PHONY: stop
stop:
	@echo "Stopping development servers..."
	@pkill -f "node src/server.js" || true
	@pkill -f "npm run dev" || true
	@pkill -f "vite" || true
	@echo "Development servers stopped"
