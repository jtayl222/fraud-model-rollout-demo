# Best Architecture Decision: Pattern 3 vs Pattern 4

## Overview

This document compares two Seldon Core v2 deployment patterns for our fraud detection project and provides a recommendation for moving forward.

## Pattern 3: Standard Scoped Operator (lc525 Recommended)

### Architecture

```mermaid
graph TB
    %% Namespaces
    subgraph "seldon-system namespace"
        SO[seldon-operator<br/>clusterwide=true<br/>watchNamespaces=fraud-detection]
        SC[ServerConfig: mlserver<br/>MLServer runtime config]
        OP[Core operator components]
    end

    subgraph "fraud-detection namespace"
        %% Runtime Components
        SS[seldon-scheduler<br/>Model scheduling]
        SM[seldon-mesh<br/>Envoy proxy]
        PG[pipeline-gateway<br/>Pipeline routing]
        MG[model-gateway<br/>Model routing]
        DE[dataflow-engine<br/>Data processing]
        
        %% Application Resources  
        SR[Server: mlserver<br/>references seldon-system/mlserver]
        M1[Model: fraud-v1-baseline<br/>TensorFlow model]
        M2[Model: fraud-v2-candidate<br/>TensorFlow model] 
        EXP[Experiment: fraud-ab-test<br/>80/20 traffic split]
        
        %% Storage
        PVC1[PVC: fraud-models-pvc<br/>Model artifacts]
        PVC2[PVC: fraud-raw-data-pvc<br/>Training data]
    end

    %% External Components
    subgraph "External Systems"
        ML[MLflow<br/>192.168.1.215:5000<br/>Model registry]
        MIN[MinIO<br/>192.168.1.200:9000<br/>S3 storage]
        MON[Prometheus/Grafana<br/>Monitoring stack]
    end

    %% Relationships
    SO --> SS
    SO --> SM
    SO --> SR
    SO --> M1
    SO --> M2
    SO --> EXP
    
    SC -.-> SR
    SR --> M1
    SR --> M2
    M1 --> PVC1
    M2 --> PVC1
    
    EXP --> M1
    EXP --> M2
    
    M1 -.-> ML
    M2 -.-> ML
    PVC1 -.-> MIN
    
    SS --> MON
    SM --> MON

    %% Styling
    classDef namespace fill:#e1f5fe
    classDef runtime fill:#f3e5f5
    classDef model fill:#e8f5e8
    classDef storage fill:#fff3e0
    classDef external fill:#fce4ec
    
    class SO,OP namespace
    class SS,SM,PG,MG,DE,SR runtime
    class M1,M2,EXP model
    class PVC1,PVC2,SC storage
    class ML,MIN,MON external
```

**Text Representation:**
```
seldon-system namespace:
├── seldon-operator (clusterwide=true, watchNamespaces=fraud-detection)
├── ServerConfig resources (centralized)
└── Core operator components

fraud-detection namespace:
├── seldon-scheduler
├── seldon-mesh (envoy)
├── pipeline-gateway
├── model-gateway
├── dataflow-engine
├── Server resources (reference ServerConfigs in seldon-system)
├── Model resources
└── Experiment resources
```

### Characteristics
- **Operator**: Lives in `seldon-system`, watches specific namespaces
- **Runtime**: Full runtime stack in each application namespace
- **ServerConfig**: Centralized in `seldon-system` namespace
- **Configuration**: `clusterwide=true` with `watchNamespaces` list

### Pros
- ✅ Officially supported by Seldon team
- ✅ Works with current Seldon Core v2.9.1 (no patches needed)
- ✅ Each namespace has its own scheduler (no single point of failure)
- ✅ Clear separation between operator and runtime

### Cons
- ❌ ServerConfigs must be managed centrally
- ❌ Application teams need platform team to modify ServerConfigs
- ❌ Less configuration isolation between teams

## Pattern 4: Enhanced Scoped Operator (Our Current Approach)

### Architecture
```
seldon-system namespace:
├── seldon-operator (clusterwide=false, watchNamespaces=[fraud-detection])
├── seldon-scheduler (shared)
├── Core operator components
└── Runtime components

fraud-detection namespace:
├── ServerConfig resources (namespace-scoped)
├── Server resources (reference local ServerConfigs)
├── Model resources
└── Experiment resources
```

### Characteristics
- **Operator**: Lives in `seldon-system`, watches specific namespaces
- **Runtime**: Shared runtime in `seldon-system`
- **ServerConfig**: Decentralized in application namespaces
- **Configuration**: `clusterwide=false` with `watchNamespaces` list

### Pros
- ✅ True configuration isolation (teams manage own ServerConfigs)
- ✅ Better multi-tenancy (complete namespace autonomy)
- ✅ Simplified runtime management (one runtime stack)
- ✅ Resource efficient (no duplicate schedulers)

### Cons
- ❌ Requires custom operator fix (not officially supported)
- ❌ Single scheduler is a potential bottleneck
- ❌ Diverges from Seldon's recommended patterns
- ❌ May break with future Seldon updates

## Key Differences

| Aspect | Pattern 3 | Pattern 4 |
|--------|-----------|-----------|
| **Operator Location** | seldon-system | seldon-system |
| **Runtime Location** | Each namespace | seldon-system only |
| **ServerConfig Location** | seldon-system | Application namespace |
| **Scheduler** | One per namespace | Shared single scheduler |
| **Official Support** | Yes | No (requires patch) |
| **Configuration Isolation** | Limited | Full |
| **Resource Usage** | Higher (duplicate runtimes) | Lower (shared runtime) |
| **Complexity** | Standard | Custom implementation |

## Current Status

We have invested significant effort in Pattern 4:
- ✅ Custom operator fix developed and tested
- ✅ Docker image built: `192.168.1.210/library/seldon-controller:fix-namespace-lookup-v4`
- ✅ Namespace structure created
- ✅ RBAC and network policies configured
- ⏳ Deployment pending

### Current Deployment Issue

```mermaid
graph TB
    subgraph "Current State (Not Working)"
        subgraph "fraud-detection namespace"
            M1[Model: fraud-v1-baseline<br/>❌ READY: False]
            M2[Model: fraud-v2-candidate<br/>❌ READY: False]
            MISSING[❌ Missing Runtime Components:<br/>• No seldon-scheduler<br/>• No seldon-mesh<br/>• No mlserver pods]
        end
        
        subgraph "seldon-system namespace"
            SO[seldon-operator<br/>✅ Running]
            SC[ServerConfig<br/>❓ Location unclear]
        end
        
        SECRETS[✅ Sealed Secrets<br/>All working now]
    end
    
    subgraph "Expected State (Pattern 3)"
        subgraph "fraud-detection namespace (target)"
            M1T[Model: fraud-v1-baseline<br/>✅ READY: True]
            M2T[Model: fraud-v2-candidate<br/>✅ READY: True]
            SST[seldon-scheduler<br/>✅ Running]
            SMT[seldon-mesh<br/>✅ Running]
            SRT[Server: mlserver<br/>✅ Running]
        end
        
        subgraph "seldon-system namespace (target)"
            SOT[seldon-operator<br/>✅ Running]
            SCT[ServerConfig: mlserver<br/>✅ Centralized location]
        end
    end
    
    style MISSING fill:#ffcdd2
    style SECRETS fill:#c8e6c9
    style M1 fill:#ffcdd2
    style M2 fill:#ffcdd2
    style M1T fill:#c8e6c9
    style M2T fill:#c8e6c9
    style SST fill:#c8e6c9
    style SMT fill:#c8e6c9
    style SRT fill:#c8e6c9
```

## Recommendation: Switch to Pattern 3

Despite our investment in Pattern 4, I recommend **switching to Pattern 3** for the following reasons:

### 1. **Project Completion**
We need to demonstrate a working fraud detection A/B test. Pattern 3 will get us there faster without custom patches.

### 2. **Supportability**
Using Seldon's recommended pattern ensures:
- Official support from Seldon team
- Compatibility with future updates
- Alignment with documentation and examples

### 3. **Production Readiness**
Pattern 3 is battle-tested and used by other organizations. Our custom Pattern 4 introduces unnecessary risk.

### 4. **Minimal Functional Impact**
For our fraud detection demo:
- We only need one ServerConfig (mlserver)
- We're not showcasing multi-tenancy features
- Configuration isolation isn't a demo requirement

## Migration Path

To switch from Pattern 4 to Pattern 3:

1. **Update Helm values** for Seldon deployment:
   ```yaml
   controller:
     clusterwide: true
     watchNamespaces: "fraud-detection"
   ```

2. **Deploy runtime components** to fraud-detection namespace:
   ```bash
   helm install seldon-core-v2-runtime seldon-core-v2-runtime \
     --namespace fraud-detection
   ```

3. **Move ServerConfig** to seldon-system:
   ```bash
   kubectl apply -f serverconfig.yaml -n seldon-system
   ```

4. **Update Server references** (no changes needed - name stays the same)

5. **Apply manifests**:
   ```bash
   kubectl apply -k k8s/base/
   ```

## Conclusion

While Pattern 4 offers superior configuration isolation, it's not worth the complexity and risk for this project. Pattern 3 provides a clear path to completion with official support. We can revisit Pattern 4 enhancements after successfully demonstrating the core fraud detection capabilities.

**Action**: Proceed with Pattern 3 to achieve project completion, then consider Pattern 4 as a future enhancement if true multi-tenancy becomes a requirement.
