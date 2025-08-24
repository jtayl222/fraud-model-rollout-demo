from diagrams import Cluster, Diagram, Edge
from diagrams.custom import Custom
from diagrams.generic.database import SQL
from diagrams.k8s.compute import Pod
from diagrams.k8s.ecosystem import Helm
from diagrams.onprem.container import Docker
from diagrams.onprem.monitoring import Grafana, Prometheus

TENSORFLOW_ICON_PATH = "./images/tensorflow_logo.png"

with Diagram(
    "Fraud Model Rollout Architecture",
    show=False,
    filename="fraud_model_rollout_diagram",
):
    # Data source
    kaggle = Custom(
        "Kaggle Fraud Dataset",
        "https://cdn-icons-png.flaticon.com/512/3135/3135715.png",
    )
    enriched = Custom(
        "Enriched Dataset\n(~1M rows)",
        "https://cdn-icons-png.flaticon.com/512/3135/3135715.png",
    )

    with Cluster("Training Phase"):
        baseline = Custom("Baseline v1\n(2023 data)", TENSORFLOW_ICON_PATH)
        candidate = Custom("Candidate v2\n(2023+Q1 2024 data)", TENSORFLOW_ICON_PATH)

        # baseline = TensorflowOnAWS("Baseline v1\n(2023 data)")
        # candidate = TensorflowOnAWS("Candidate v2\n(2023+Q1 2024 data)")
        holdout = Custom(
            "Holdout Test\nFeb–Mar 2024",
            "https://cdn-icons-png.flaticon.com/512/906/906334.png",
        )

    with Cluster("Kubernetes Cluster"):
        seldon_ab = Helm("Seldon Core\nA/B Deployment")
        with Cluster("Predictors"):
            baseline_serving = Docker("TF Serving v1")
            candidate_serving = Docker("TF Serving v2")

        replay = Pod("Fast Transaction\nReplay")
        feedback = Pod("Feedback API\nDelayed Ground Truth")

        monitoring = [Prometheus("Prometheus"), Grafana("Grafana")]

    # Feedback store (ground truth)
    db = SQL("Feedback DB")

    # Promotion decision
    decision = Custom(
        "Promotion Decision", "https://cdn-icons-png.flaticon.com/512/992/992700.png"
    )

    # Connections
    kaggle >> enriched >> [baseline, candidate]
    baseline >> holdout
    candidate >> holdout >> decision

    decision >> seldon_ab
    seldon_ab >> [baseline_serving, candidate_serving]

    replay >> Edge(label="80/20 Traffic") >> seldon_ab
    seldon_ab >> feedback >> db

    feedback >> monitoring
    db >> monitoring
    monitoring >> decision
