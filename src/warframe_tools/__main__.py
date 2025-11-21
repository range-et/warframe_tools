"""CLI entry point for warframe_tools."""

import sys
from .workflows import run_dependency_workflow


def main():
    """Main CLI entry point."""
    if len(sys.argv) > 1 and sys.argv[1] == 'dependency':
        # Run dependency workflow
        result = run_dependency_workflow()
        print(f"\n✓ Workflow completed successfully!")
        print(f"  Visualization saved to: {result['visualization_file']}")
        return 0
    else:
        print("Warframe Tools CLI")
        print("\nUsage:")
        print("  python -m warframe_tools dependency  - Run dependency analysis workflow")
        print("\nOr use as a library:")
        print("  from warframe_tools.workflows import run_dependency_workflow")
        print("  run_dependency_workflow()")
        return 1


if __name__ == "__main__":
    sys.exit(main())

